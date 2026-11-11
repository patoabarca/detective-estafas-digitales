"""
Módulo de Minimización y Ocultamiento Preventivo de Datos Sensibles (PII Masking).

Antes de enviar texto al proveedor externo de IA (Google Gemini API):
1. Oculta patrones evidentes de datos personales o bancarios innecesarios para la
   orquestación/preparación (CBU/CVU de 22 dígitos, tarjetas de 13-19 dígitos,
   direcciones de correo personales, teléfonos y números de DNI/CUIT).
2. Conserva la estructura de las direcciones web (URLs) y del mensaje, ocultando
   credenciales embebidas (`user:pass@host`) y valores sensibles en rutas, parámetros
   (`query`) o fragmentos (`#fragment`) de las URLs antes de enviarlas al LLM externo.
3. El texto y las URLs originales sin enmascarar se conservan exclusivamente en memoria
   RAM local para el análisis determinístico local, sin escribirse en logs ni trazas.

Nota de honestidad técnica: El ocultamiento por expresiones regulares reduce la
exposición de datos frecuentes, pero NO garantiza eliminar el 100% de los datos
sensibles posibles en texto libre.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Tuple
from urllib.parse import urlsplit, urlunsplit

from scripts.url_analyzer import extract_urls


# Expresiones regulares para patrones sensibles comunes
CBU_CVU_REGEX = re.compile(r"\b\d{22}\b")
CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
CUIT_CUIL_REGEX = re.compile(r"\b(?:20|23|24|27|30|33|34)-\d{8}-\d\b")
DNI_REGEX = re.compile(r"(?i)\b(?:dni|documento)\s*[:#º°]?\s*(\d{1,2}\.?\d{3}\.?\d{3}|\d{7,8})\b")
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_REGEX = re.compile(r"(?:\+?54\s*9?\s*)?(?:\(?0?\d{2,4}\)?[\s-]*)?\d{3,4}[\s-]+\d{4}\b")
URL_SENSITIVE_PARAM_REGEX = re.compile(
    r"(?i)((?:token|access_token|id_token|auth|jwt|pass|password|pwd|clave|pin|otp|dni|cuit|cuil|cbu|cvu|email|correo|user|usuario|session|sesion|key|secret)=)([^&#\s]+)"
)
URL_PATH_SENSITIVE_SEGMENT_REGEX = re.compile(
    r"(?i)(/(?:token|reset|verify|confirm|auth|session|sesion|clave|otp|dni|cliente|usuario|user|id|cuenta)/)([A-Za-z0-9._~-]{6,})"
)


def _redact_url_component(comp: str) -> Tuple[str, int]:
    """Oculta parámetros sensibles, correos, CBU/CVU, CUIT y tarjetas dentro de path/query/fragment."""
    if not comp:
        return "", 0
    updated = comp
    count = 0

    def _sub_and_count(pat: re.Pattern, repl: str, s: str) -> Tuple[str, int]:
        matches = len(pat.findall(s))
        if matches > 0:
            return pat.sub(repl, s), matches
        return s, 0

    updated, c1 = _sub_and_count(URL_SENSITIVE_PARAM_REGEX, r"\1[VALOR_URL_OCULTO]", updated)
    updated, c2 = _sub_and_count(URL_PATH_SENSITIVE_SEGMENT_REGEX, r"\1[TOKEN_RUTA_OCULTO]", updated)
    updated, c3 = _sub_and_count(EMAIL_REGEX, "[EMAIL_OCULTO]", updated)
    updated, c4 = _sub_and_count(CBU_CVU_REGEX, "[CBU_CVU_OCULTO]", updated)
    updated, c5 = _sub_and_count(CUIT_CUIL_REGEX, "[CUIT_OCULTO]", updated)
    updated, c6 = _sub_and_count(DNI_REGEX, "DNI [DNI_OCULTO]", updated)
    count = c1 + c2 + c3 + c4 + c5 + c6
    return updated, count


def sanitize_url_for_external_llm(url: str) -> Tuple[str, int]:
    """
    Oculta credenciales embebidas (`user:pass@host`) y parámetros o valores sensibles
    en rutas (`path`), `query` y `fragment` de una URL (o componentes/evidencias aisladas)
    antes de enviarla al modelo externo, conservando el esquema, dominio y estructura.
    Devuelve la URL sanitizada y la cantidad de ocultamientos aplicados.
    El enlace original se mantiene intacto en memoria local para `url_analyzer`.
    """
    if not url:
        return "", 0

    redactions_count = 0
    working = url.strip()
    try:
        has_scheme = "://" in working
        parts = urlsplit(working if has_scheme else f"http://{working}")
        netloc = parts.netloc
        if "@" in netloc:
            _, _, hostpart = netloc.rpartition("@")
            netloc = f"[CREDENCIAL_URL_OCULTA]@{hostpart}"
            redactions_count += 1

        path, path_count = _redact_url_component(parts.path)
        query, query_count = _redact_url_component(parts.query)
        fragment, frag_count = _redact_url_component(parts.fragment)
        redactions_count += (path_count + query_count + frag_count)

        # Si no había esquema original, netloc podría contener una query o fragmento aislado
        # (por ejemplo, 'token=123&x=1' donde urlsplit ubica todo en netloc al no haber '/' o '?').
        if not has_scheme:
            netloc, netloc_count = _redact_url_component(netloc)
            redactions_count += netloc_count

        rebuilt = urlunsplit((parts.scheme if has_scheme else "", netloc, path, query, fragment))
        if not has_scheme and rebuilt.startswith("//"):
            rebuilt = rebuilt[2:]
        return rebuilt, redactions_count
    except Exception:
        fallback, fb_count = _redact_url_component(working)
        return fallback, fb_count


def build_session_url_maps(urls: List[str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Construye de forma determinística y estable la correspondencia entre identificadores de sesión
    ('URL-1', 'URL-2', ...), las URLs originales locales y sus representaciones sanitizadas para el modelo.
    Conserva el orden canónico y el aislamiento de sesión sin estado global compartido.
    """
    url_id_map: Dict[str, str] = {}
    masked_url_id_map: Dict[str, str] = {}
    for idx, raw_u in enumerate(urls, start=1):
        uid = f"URL-{idx}"
        url_id_map[uid] = raw_u
        masked_url_id_map[uid] = sanitize_url_for_external_llm(raw_u)[0]
    return url_id_map, masked_url_id_map


def sanitize_url_component_for_external_llm(component: str) -> Tuple[str, int]:
    """
    Oculta credenciales, parámetros sensibles, tokens de ruta y datos sensibles
    en un componente, fragmento o evidencia de URL aislada (query, netloc, path, userinfo).
    Devuelve el componente sanitizado y la cantidad de ocultamientos aplicados.
    """
    if not component:
        return "", 0
    return sanitize_url_for_external_llm(component)


@dataclass
class SanitizationReport:
    """Resumen transparente de qué se enmascaró antes de enviar al proveedor externo."""
    masked_text: str
    redactions_count: int = 0
    redacted_categories: List[str] = field(default_factory=list)
    sent_char_count: int = 0
    provider_name: str = "Google Gemini API"
    disclaimer: str = (
        "Se enviaron al proveedor externo únicamente metadatos de control y el texto con "
        "ocultamiento preventivo de patrones numéricos/personales comunes (CBU/CVU, tarjetas, "
        "CUIT/DNI, correos, teléfonos y credenciales/tokens en URLs). Las imágenes nunca se envían "
        "a la API (se procesan con Tesseract OCR local). Importante: el ocultamiento automático "
        "reduce la exposición, pero no garantiza eliminar todos los datos sensibles que pudieran "
        "escribirse en texto libre."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "sent_char_count": self.sent_char_count,
            "redactions_count": self.redactions_count,
            "redacted_categories": list(self.redacted_categories),
            "masked_preview": (
                self.masked_text[:280] + ("..." if len(self.masked_text) > 280 else "")
            ),
            "disclaimer": self.disclaimer,
        }


def sanitize_text_for_external_llm(
    text: str,
    provider_name: str = "Google Gemini API",
) -> SanitizationReport:
    """
    Oculta datos personales/financieros obvios preservando el dominio y estructura de las URLs
    del mensaje (pero redactando credenciales, tokens o correos dentro de las URLs).
    """
    if not text:
        return SanitizationReport(
            masked_text="",
            redactions_count=0,
            redacted_categories=[],
            sent_char_count=0,
            provider_name=provider_name,
        )

    # 1. Proteger temporalmente las URLs para no alterar dominios o rutas con números
    urls = extract_urls(text)
    url_placeholders: Dict[str, str] = {}
    working = text
    for idx, url in enumerate(urls):
        token = f"__URL_PLACEHOLDER_{idx}__"
        url_placeholders[token] = url
        working = working.replace(url, token)

    redactions = 0
    categories: List[str] = []

    def _apply_mask(pattern: re.Pattern, replacement: str, category_label: str, current: str) -> str:
        nonlocal redactions
        matches = list(pattern.finditer(current))
        if matches:
            redactions += len(matches)
            if category_label not in categories:
                categories.append(category_label)
            return pattern.sub(replacement, current)
        return current

    # Orden de especificidad: CBU/CVU (22 dígitos) -> CUIT/CUIL -> Tarjetas -> DNI -> Email -> Teléfonos
    working = _apply_mask(CBU_CVU_REGEX, "[CBU_CVU_OCULTO]", "CBU/CVU", working)
    working = _apply_mask(CUIT_CUIL_REGEX, "[CUIT_OCULTO]", "CUIT/CUIL", working)
    working = _apply_mask(CARD_REGEX, "[TARJETA_OCULTA]", "Tarjeta bancaria", working)
    working = _apply_mask(DNI_REGEX, "DNI [DNI_OCULTO]", "DNI", working)
    working = _apply_mask(EMAIL_REGEX, "[EMAIL_OCULTO]", "Correo electrónico", working)
    working = _apply_mask(PHONE_REGEX, "[TELEFONO_OCULTO]", "Teléfono", working)

    # Restaurar las URLs con sanitización preventiva de credenciales o parámetros sensibles
    for token, original_url in url_placeholders.items():
        safe_url, url_redacted = sanitize_url_for_external_llm(original_url)
        if url_redacted:
            redactions += 1
            if "Credenciales/Parámetros en URL" not in categories:
                categories.append("Credenciales/Parámetros en URL")
        working = working.replace(token, safe_url)

    return SanitizationReport(
        masked_text=working,
        redactions_count=redactions,
        redacted_categories=categories,
        sent_char_count=len(working),
        provider_name=provider_name,
    )


def sanitize_snippets_for_external_llm(snippets: List[str]) -> List[str]:
    """
    Aplica enmascaramiento preventivo de PII a fragmentos de evidencia antes de
    incluirlos en la respuesta de una herramienta que vuelve al modelo externo.
    """
    sanitized: List[str] = []
    for s in snippets or []:
        rep = sanitize_text_for_external_llm(str(s))
        sanitized.append(rep.masked_text)
    return sanitized
