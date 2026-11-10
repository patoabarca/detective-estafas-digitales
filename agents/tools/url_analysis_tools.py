"""
Herramientas Python Reutilizables para el Agente Analizador de Enlaces (Etapa 3).

Corresponde 1-a-1 con la Skill `.agents/skills/analizar-url/SKILL.md`:
- `tool_analizar_url` -> `analizar-url`

Principios de Reutilización, Seguridad y Privacidad:
- Reutiliza directamente `analyze_single_url` de `scripts/url_analyzer.py` (Zero Network: nunca visita URLs).
- Opera sobre el mapa validado de referencias en `PreparationSessionContext` (`ctx.url_id_map`).
- Rechaza mediante `ContractValidationError` cualquier `url_id` inexistente o cualquier dirección
  web inventada o sustituida por el modelo.
- Soporta procesamiento en lote acotado (`url_ids: List[str]`, hasta `MAX_URLS_PER_CALL` enlaces,
  o `["ALL"]` para procesar todas las URLs de la sesión en una única llamada), evitando un turno de
  modelo por cada URL.
- Deduplica referencias repetidas en la misma llamada o entre llamadas sucesivas para evitar
  duplicar hallazgos o puntuaciones.
- Conserva intacta cualquier URL dudosa extraída por OCR sin autocorregirla y adjunta sus advertencias.
- Distingue explícitamente:
  * Enlace analizado con señales de riesgo (`analizado_con_senales`).
  * Enlace analizado sin señales de riesgo (`analizado_sin_senales`).
  * Dirección malformada o sin dominio identificable (`direccion_no_analizable`).
  * Fallo técnico de herramienta (`error_herramienta`).
- Antes de devolver la respuesta de la herramienta al modelo externo, sanitiza las URLs y evidencias
  con `sanitize_url_for_external_llm` y `sanitize_text_for_external_llm`, conservando los originales
  en memoria local para el motor determinístico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Callable, Dict, List, Optional
import urllib.parse

from agents.common.contracts import (
    ContractValidationError,
    UrlItemAnalysisResult,
    UrlSignalFinding,
    validate_tool_arguments,
)
from agents.common.privacy import (
    sanitize_text_for_external_llm,
    sanitize_url_component_for_external_llm,
    sanitize_url_for_external_llm,
)
from agents.tools.preparation_tools import PreparationSessionContext
from scripts.url_analyzer import analyze_single_url

MAX_URLS_PER_CALL = 20

NON_GUARANTEE_WARNING = (
    "La ausencia de señales sintácticas en un enlace NO garantiza que el sitio web sea legítimo o seguro."
)


@dataclass
class UrlAnalysisSessionState:
    """
    Estado aislado en memoria para la ejecución del Agente Analizador de Enlaces.
    Registra cada enlace procesado por su `url_id` sin duplicar análisis ni puntajes.
    """
    analyzed_items_by_id: Dict[str, UrlItemAnalysisResult] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    tools_called: List[str] = field(default_factory=list)
    tool_errors: List[str] = field(default_factory=list)


def _extract_concrete_evidence(raw_url: str, domain: str, finding_text: str) -> str:
    """
    Obtiene el fragmento concreto de la URL (`raw_url` o `domain`) que respalda el hallazgo,
    garantizando que exista literalmente en `raw_url` o `domain`.
    """
    parsed = urllib.parse.urlparse(raw_url)

    # Si el hallazgo cita un término entre comillas simples (ej. marca o keyword o tld)
    quoted = re.findall(r"'([^']+)'", finding_text)
    for q in quoted:
        if q in raw_url or (domain and q in domain):
            return q

    # Si cita una extensión entre paréntesis como (.xyz)
    tld_match = re.search(r"\(\.([a-z0-9]+)\)", finding_text)
    if tld_match:
        dot_tld = f".{tld_match.group(1)}"
        if dot_tld in raw_url or (domain and dot_tld in domain):
            return dot_tld

    # Si es hallazgo de userinfo (usuario:contraseña@host)
    if "credenciales embebidas" in finding_text and "@" in raw_url:
        netloc = parsed.netloc
        if netloc and netloc in raw_url:
            return netloc

    # Si es hallazgo de parámetros sensibles en query string
    if "parámetros sensibles" in finding_text and parsed.query and parsed.query in raw_url:
        return parsed.query

    # Si es protocolo HTTP o HTTPS
    if "Utiliza HTTP " in finding_text and raw_url.lower().startswith("http://"):
        return raw_url[:7]
    if "Utiliza HTTPS" in finding_text and raw_url.lower().startswith("https://"):
        return raw_url[:8]

    # Por defecto usar el dominio si está presente en raw_url, o la raw_url completa
    if domain and domain != "no_identificado" and domain in raw_url.lower():
        # Buscar la subcadena exacta en raw_url (respetando mayúsculas/minúsculas originales)
        idx = raw_url.lower().find(domain.lower())
        if idx != -1:
            return raw_url[idx : idx + len(domain)]
        return domain

    return raw_url


def _map_findings_to_signals_and_rules(
    raw_url: str,
    url_dict: Dict[str, Any],
) -> tuple[List[UrlSignalFinding], List[str]]:
    """
    Traduce el diccionario devuelto por `analyze_single_url(raw_url)` a objetos
    `UrlSignalFinding` con identificadores de reglas estables (`REGLA-URL-01`..`REGLA-URL-05`
    e informativos), respetando exactamente la lógica de `RiskClassifier`.
    """
    findings: List[str] = url_dict.get("findings", [])
    domain: str = url_dict.get("domain", "no_identificado")
    is_ip: bool = bool(url_dict.get("is_ip_address", False))
    has_puny: bool = bool(url_dict.get("has_punycode", False))
    has_userinfo: bool = bool(url_dict.get("has_userinfo", False))

    has_misleading_subdomain = any(
        "Uso engañoso" in f or "términos engañosos" in f for f in findings
    )
    has_suspicious_tld = any("extensión de dominio de bajo costo" in f for f in findings)

    signals: List[UrlSignalFinding] = []
    activated_rules: List[str] = []

    # 1. REGLA-URL-01: IP directa
    if is_ip:
        ip_desc = next(
            (f for f in findings if "dirección IP" in f),
            f"El enlace apunta directamente a una dirección IP ({domain}).",
        )
        ev = _extract_concrete_evidence(raw_url, domain, ip_desc)
        sig = UrlSignalFinding(
            id_regla="REGLA-URL-01",
            tipo_senal="riesgo_ip_directa",
            evidencia=ev,
            descripcion=ip_desc,
        )
        sig.validate(raw_url=raw_url, domain=domain)
        signals.append(sig)
        activated_rules.append("REGLA-URL-01")

    # 2. REGLA-URL-02: Subdominio engañoso (marca o keyword de seguridad)
    if has_misleading_subdomain:
        sub_findings = [
            f for f in findings if "Uso engañoso" in f or "términos engañosos" in f
        ]
        for sf in sub_findings:
            ev = _extract_concrete_evidence(raw_url, domain, sf)
            sig = UrlSignalFinding(
                id_regla="REGLA-URL-02",
                tipo_senal="riesgo_subdominio_enganoso",
                evidencia=ev,
                descripcion=sf,
            )
            sig.validate(raw_url=raw_url, domain=domain)
            signals.append(sig)
        activated_rules.append("REGLA-URL-02")

    # 3. REGLA-URL-03: Punycode o caracteres homóglifos
    if has_puny:
        puny_desc = next(
            (f for f in findings if "Punycode" in f or "homóglifos" in f),
            "El dominio utiliza codificación Punycode o caracteres homóglifos.",
        )
        ev = _extract_concrete_evidence(raw_url, domain, puny_desc)
        sig = UrlSignalFinding(
            id_regla="REGLA-URL-03",
            tipo_senal="riesgo_punycode_homoglifos",
            evidencia=ev,
            descripcion=puny_desc,
        )
        sig.validate(raw_url=raw_url, domain=domain)
        signals.append(sig)
        activated_rules.append("REGLA-URL-03")

    # 4. REGLA-URL-04: Credenciales embebidas (user:pass@host)
    if has_userinfo:
        ui_desc = next(
            (f for f in findings if "credenciales embebidas" in f),
            "La URL contiene credenciales embebidas (patrón usuario:contraseña@host).",
        )
        ev = _extract_concrete_evidence(raw_url, domain, ui_desc)
        sig = UrlSignalFinding(
            id_regla="REGLA-URL-04",
            tipo_senal="riesgo_credenciales_embebidas",
            evidencia=ev,
            descripcion=ui_desc,
        )
        sig.validate(raw_url=raw_url, domain=domain)
        signals.append(sig)
        activated_rules.append("REGLA-URL-04")

    # 5. REGLA-URL-05: TLD de bajo costo / sospechoso
    if has_suspicious_tld:
        tld_desc = next(
            (f for f in findings if "extensión de dominio de bajo costo" in f),
            "El dominio utiliza una extensión de dominio de bajo costo.",
        )
        ev = _extract_concrete_evidence(raw_url, domain, tld_desc)
        sig = UrlSignalFinding(
            id_regla="REGLA-URL-05",
            tipo_senal="riesgo_tld_sospechoso",
            evidencia=ev,
            descripcion=tld_desc,
        )
        sig.validate(raw_url=raw_url, domain=domain)
        signals.append(sig)
        # En RiskClassifier, REGLA-URL-05 suma puntos solo si no se activó REGLA-URL-02
        if not has_misleading_subdomain:
            activated_rules.append("REGLA-URL-05")

    # 6. Hallazgos informativos (no suman puntaje directo en RiskClassifier pero documentan estructura)
    for f in findings:
        if "parámetros sensibles" in f:
            ev = _extract_concrete_evidence(raw_url, domain, f)
            sig = UrlSignalFinding(
                id_regla="INFO-URL-SENSITIVE-PARAMS",
                tipo_senal="informativa_parametros_sensibles",
                evidencia=ev,
                descripcion=f,
            )
            sig.validate(raw_url=raw_url, domain=domain)
            signals.append(sig)
        elif "Utiliza HTTP sin cifrado" in f:
            ev = _extract_concrete_evidence(raw_url, domain, f)
            sig = UrlSignalFinding(
                id_regla="INFO-URL-HTTP",
                tipo_senal="informativa_http_sin_cifrado",
                evidencia=ev,
                descripcion=f,
            )
            sig.validate(raw_url=raw_url, domain=domain)
            signals.append(sig)

    return signals, activated_rules


def _match_ocr_warnings_for_url(
    raw_url: str,
    domain: str,
    ocr_url_warnings: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    """
    Asocia advertencias de distorsión tipográfica OCR (`ocr_url_warnings`) correspondientes
    al enlace actual sin autocorregir la URL original.
    """
    matched: List[Dict[str, str]] = []
    for uw in ocr_url_warnings or []:
        snippet = (uw.get("snippet") or "").strip()
        if not snippet:
            matched.append(dict(uw))
            continue
        if (
            snippet.lower() in raw_url.lower()
            or raw_url.lower() in snippet.lower()
            or (domain and domain != "no_identificado" and domain.lower() in snippet.lower())
        ):
            matched.append(dict(uw))
    # Si hay advertencias OCR de URL en la sesión y ninguna matcheó por subcadena exacta,
    # adjuntarlas igualmente para no perder ninguna advertencia de OCR sobre enlaces dudosos.
    if not matched and ocr_url_warnings:
        matched = [dict(uw) for uw in ocr_url_warnings]
    return matched


def _is_unparseable_or_malformed_url(raw_url: str, analyzed: Dict[str, Any]) -> Optional[str]:
    """
    Verifica si una dirección extraída carece de estructura mínima analizable
    (por ejemplo, sin hostname identificable, caracteres de espacio internos o esquema roto).
    """
    domain = analyzed.get("domain", "no_identificado")
    if not domain or domain == "no_identificado":
        return "La dirección no contiene un nombre de host o dominio identificable."
    # Hostname sin punto ni IP válida
    if not analyzed.get("is_ip_address", False) and "." not in domain:
        return f"El host '{domain}' no posee una estructura de dominio o dirección IP válida."
    if any(ch.isspace() for ch in raw_url.strip()):
        return "La dirección contiene espacios en blanco internos que impiden su análisis como URL válida."
    return None


def execute_tool_analizar_url(
    prep_ctx: PreparationSessionContext,
    url_state: UrlAnalysisSessionState,
    raw_args: Optional[Dict[str, Any]] = None,
    url_analyzer_override: Optional[Callable[[str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Herramienta Python de la skill `analizar-url`.
    Recupera las URLs originales del estado local validado (`prep_ctx.url_id_map`)
    y ejecuta `analyze_single_url` de `scripts/url_analyzer.py` sin realizar conexiones de red.
    """
    validated_args = validate_tool_arguments(
        tool_name="tool_analizar_url",
        args=raw_args,
        allowed_params={"url_ids": list},
        required_params=["url_ids"],
    )
    url_state.tools_called.append("tool_analizar_url")

    requested_ids_raw = validated_args.get("url_ids", [])
    if not isinstance(requested_ids_raw, list) or len(requested_ids_raw) == 0:
        raise ContractValidationError(
            "El parámetro 'url_ids' en 'tool_analizar_url' debe ser una lista no vacía de identificadores."
        )
    if len(requested_ids_raw) > MAX_URLS_PER_CALL:
        raise ContractValidationError(
            f"La lista 'url_ids' ({len(requested_ids_raw)} elementos) supera el límite máximo "
            f"de {MAX_URLS_PER_CALL} enlaces por llamada."
        )
    if not all(isinstance(item, str) and item.strip() for item in requested_ids_raw):
        raise ContractValidationError(
            "Todos los elementos de 'url_ids' en 'tool_analizar_url' deben ser cadenas no vacías."
        )

    # Asegurar que el mapa de referencias exista si extracted_urls fue poblado
    if not prep_ctx.url_id_map and prep_ctx.extracted_urls:
        prep_ctx.url_id_map = {
            f"URL-{idx}": u for idx, u in enumerate(prep_ctx.extracted_urls, start=1)
        }
        prep_ctx.masked_url_id_map = {
            uid: sanitize_url_for_external_llm(u)[0]
            for uid, u in prep_ctx.url_id_map.items()
        }

    if not prep_ctx.url_id_map:
        return {
            "status": "no_links",
            "processed_count": 0,
            "total_session_links": 0,
            "pending_url_ids": [],
            "results": [],
            "error_message": None,
        }

    # Resolver "ALL" o validar que cada identificador pertenezca a prep_ctx.url_id_map.
    # Rechazar cualquier URL inventada o sustituida por el modelo.
    resolved_ids: List[str] = []
    for req_id in requested_ids_raw:
        clean_id = req_id.strip()
        if clean_id.upper() == "ALL":
            for uid in prep_ctx.url_id_map.keys():
                if uid not in resolved_ids:
                    resolved_ids.append(uid)
        elif clean_id in prep_ctx.url_id_map:
            if clean_id not in resolved_ids:
                resolved_ids.append(clean_id)
        else:
            raise ContractValidationError(
                f"Identificador de enlace inválido, inexistente o URL sustituida rechazada: '{clean_id}'. "
                f"Identificadores válidos en la sesión: {list(prep_ctx.url_id_map.keys())}"
            )

    analyzer_fn = url_analyzer_override or analyze_single_url
    sanitized_results_for_llm: List[Dict[str, Any]] = []

    try:
        for uid in resolved_ids:
            # Si ya fue procesado en una llamada previa dentro de la misma sesión,
            # reutilizar el resultado para no duplicar hallazgos ni puntajes.
            if uid in url_state.analyzed_items_by_id:
                existing_item = url_state.analyzed_items_by_id[uid]
                sanitized_results_for_llm.append(
                    _build_sanitized_item_for_llm(existing_item)
                )
                continue

            raw_url = prep_ctx.url_id_map[uid]
            masked_url = prep_ctx.masked_url_id_map.get(uid) or sanitize_url_for_external_llm(raw_url)[0]

            try:
                raw_analysis = analyzer_fn(raw_url)
            except ValueError as val_err:
                # Por ejemplo, puerto inválido en urllib.parse (http://dominio.com:99999) o IP malformada
                unparseable_reason = (
                    f"La dirección '{masked_url}' tiene un formato inválido y no pudo analizarse: {str(val_err)}"
                )
                ocr_warns = _match_ocr_warnings_for_url(
                    raw_url, "no_identificado", prep_ctx.ocr_url_warnings
                )
                item_warns = [unparseable_reason]
                for ow in ocr_warns:
                    exp = ow.get("explanation")
                    if exp and exp not in item_warns:
                        item_warns.append(exp)
                for w in item_warns:
                    if w not in url_state.warnings:
                        url_state.warnings.append(w)

                item_res = UrlItemAnalysisResult(
                    url_id=uid,
                    raw_url=raw_url,
                    masked_url=masked_url,
                    estado_enlace="direccion_no_analizable",
                    scheme="desconocido",
                    domain="no_identificado",
                    port=None,
                    is_ip_address=False,
                    has_punycode=False,
                    has_userinfo=False,
                    findings=[unparseable_reason],
                    senales_encontradas=[],
                    reglas_activadas=[],
                    advertencias=item_warns,
                    ocr_warnings=ocr_warns,
                )
                item_res.validate(allowed_raw_urls=prep_ctx.extracted_urls)
                url_state.analyzed_items_by_id[uid] = item_res
                sanitized_results_for_llm.append(_build_sanitized_item_for_llm(item_res))
                continue

            malformed_reason = _is_unparseable_or_malformed_url(raw_url, raw_analysis)
            domain = raw_analysis.get("domain", "no_identificado")
            ocr_warns = _match_ocr_warnings_for_url(raw_url, domain, prep_ctx.ocr_url_warnings)

            if malformed_reason is not None:
                item_warns = [malformed_reason]
                for ow in ocr_warns:
                    exp = ow.get("explanation")
                    if exp and exp not in item_warns:
                        item_warns.append(exp)
                for w in item_warns:
                    if w not in url_state.warnings:
                        url_state.warnings.append(w)

                item_res = UrlItemAnalysisResult(
                    url_id=uid,
                    raw_url=raw_url,
                    masked_url=masked_url,
                    estado_enlace="direccion_no_analizable",
                    scheme=raw_analysis.get("scheme", "desconocido"),
                    domain=domain,
                    port=raw_analysis.get("port"),
                    is_ip_address=bool(raw_analysis.get("is_ip_address", False)),
                    has_punycode=bool(raw_analysis.get("has_punycode", False)),
                    has_userinfo=bool(raw_analysis.get("has_userinfo", False)),
                    findings=list(raw_analysis.get("findings", [])) + [malformed_reason],
                    senales_encontradas=[],
                    reglas_activadas=[],
                    advertencias=item_warns,
                    ocr_warnings=ocr_warns,
                )
                item_res.validate(allowed_raw_urls=prep_ctx.extracted_urls)
                url_state.analyzed_items_by_id[uid] = item_res
                sanitized_results_for_llm.append(_build_sanitized_item_for_llm(item_res))
                continue

            signals, activated_rules = _map_findings_to_signals_and_rules(raw_url, raw_analysis)
            # Determinar si tiene señales de riesgo (REGLA-URL-01..05 o parámetros sensibles)
            has_risk_signals = bool(activated_rules) or any(
                s.id_regla == "INFO-URL-SENSITIVE-PARAMS" for s in signals
            )
            estado_enlace = (
                "analizado_con_senales" if has_risk_signals else "analizado_sin_senales"
            )

            item_warns: List[str] = []
            for f_str in raw_analysis.get("findings", []):
                if "HTTPS" not in f_str:
                    w_msg = f"URL [{domain}]: {f_str}"
                    item_warns.append(w_msg)
                    if w_msg not in url_state.warnings:
                        url_state.warnings.append(w_msg)
                    if w_msg not in prep_ctx.warnings:
                        prep_ctx.warnings.append(w_msg)

            for ow in ocr_warns:
                exp = ow.get("explanation")
                if exp:
                    if exp not in item_warns:
                        item_warns.append(exp)
                    if exp not in url_state.warnings:
                        url_state.warnings.append(exp)

            if estado_enlace == "analizado_sin_senales":
                if NON_GUARANTEE_WARNING not in item_warns:
                    item_warns.append(NON_GUARANTEE_WARNING)
                if NON_GUARANTEE_WARNING not in url_state.warnings:
                    url_state.warnings.append(NON_GUARANTEE_WARNING)

            item_res = UrlItemAnalysisResult(
                url_id=uid,
                raw_url=raw_url,
                masked_url=masked_url,
                estado_enlace=estado_enlace,  # type: ignore[arg-type]
                scheme=raw_analysis.get("scheme", "desconocido"),
                domain=domain,
                port=raw_analysis.get("port"),
                is_ip_address=bool(raw_analysis.get("is_ip_address", False)),
                has_punycode=bool(raw_analysis.get("has_punycode", False)),
                has_userinfo=bool(raw_analysis.get("has_userinfo", False)),
                findings=list(raw_analysis.get("findings", [])),
                senales_encontradas=signals,
                reglas_activadas=activated_rules,
                advertencias=item_warns,
                ocr_warnings=ocr_warns,
            )
            item_res.validate(allowed_raw_urls=prep_ctx.extracted_urls)
            url_state.analyzed_items_by_id[uid] = item_res
            sanitized_results_for_llm.append(_build_sanitized_item_for_llm(item_res))

        # Sincronizar prep_ctx.url_details con los análisis realizados para compatibilidad
        prep_ctx.url_details = [
            it.to_engine_url_dict() for it in url_state.analyzed_items_by_id.values()
        ]

        # Determinar enlaces pendientes en la sesión (para que el modelo decida continuación si fue un lote parcial)
        pending_ids = [
            uid for uid in prep_ctx.url_id_map.keys()
            if uid not in url_state.analyzed_items_by_id
        ]

        return {
            "status": "ok",
            "processed_count": len(sanitized_results_for_llm),
            "total_session_links": len(prep_ctx.url_id_map),
            "pending_url_ids": pending_ids,
            "results": sanitized_results_for_llm,
            "error_message": None,
        }

    except ContractValidationError:
        raise
    except Exception as exc:
        err_msg = f"Fallo en tool_analizar_url: {str(exc)}"
        url_state.tool_errors.append(err_msg)
        pending_ids = [
            uid for uid in prep_ctx.url_id_map.keys()
            if uid not in url_state.analyzed_items_by_id
        ]
        return {
            "status": "tool_error",
            "processed_count": 0,
            "total_session_links": len(prep_ctx.url_id_map),
            "pending_url_ids": pending_ids,
            "results": [],
            "error_message": err_msg,
        }


def _build_sanitized_item_for_llm(item: UrlItemAnalysisResult) -> Dict[str, Any]:
    """
    Construye la representación sanitizada y compacta de un `UrlItemAnalysisResult`
    para ser enviada al modelo externo en `function_response`.
    Elimina duplicaciones entre señales, advertencias por ítem y advertencias globales:
    - Conserva identificador, URL sanitizada, estado del enlace, esquema, dominio y reglas activadas.
    - Conserva evidencias sanitizadas y tipos de señal sin duplicar descripciones redundantes.
    - Solo incluye advertencias no redundantes (ej. formato no analizable u OCR) cuando no
      deriven directamente de las reglas ya informadas.
    - Preserva la corrección de privacidad sanitizando cualquier valor sensible residual.
    """
    safe_signals = []
    for s in item.senales_encontradas:
        safe_ev = sanitize_url_component_for_external_llm(s.evidencia)[0]
        safe_ev = sanitize_text_for_external_llm(safe_ev).masked_text
        safe_signals.append(
            {
                "id_regla": s.id_regla,
                "tipo_senal": s.tipo_senal,
                "evidencia": safe_ev,
            }
        )

    # Identificar advertencias específicas no redundantes (ej. error de formato o distorsión OCR)
    specific_warnings: List[str] = []
    if item.estado_enlace == "direccion_no_analizable":
        for w in item.advertencias:
            safe_w = sanitize_text_for_external_llm(
                sanitize_url_component_for_external_llm(w)[0]
            ).masked_text
            if safe_w not in specific_warnings:
                specific_warnings.append(safe_w)
    elif item.ocr_warnings:
        for ow in item.ocr_warnings:
            exp = ow.get("explanation")
            if exp:
                safe_exp = sanitize_text_for_external_llm(exp).masked_text
                if safe_exp not in specific_warnings:
                    specific_warnings.append(safe_exp)

    res: Dict[str, Any] = {
        "url_id": item.url_id,
        "masked_url": item.masked_url,
        "estado_enlace": item.estado_enlace,
        "scheme": item.scheme,
        "domain": item.domain,
        "reglas_activadas": list(item.reglas_activadas),
        "senales_encontradas": safe_signals,
    }
    if specific_warnings:
        res["advertencias_especificas"] = specific_warnings
    return res

