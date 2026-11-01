"""
Herramientas Python Reutilizables para el Agente Analizador de Mensajes (Etapa 2).

Cada una de las 5 herramientas corresponde 1-a-1 con una Skill independiente en `.agents/skills/`:
1. `tool_detectar_urgencia`       -> `detectar-urgencia`       (`ING-URGENCIA-ARTIFICIAL`)
2. `tool_detectar_amenazas`       -> `detectar-amenazas`       (`ING-AMENAZA-BLOQUEO`)
3. `tool_detectar_premios`        -> `detectar-premios`        (`FRA-PREMIO-INESPERADO`)
4. `tool_detectar_pedidos_datos`  -> `detectar-pedidos-datos`  (`FRA-CAPTURA-CREDENCIALES`)
5. `tool_detectar_pedidos_dinero` -> `detectar-pedidos-dinero` (`FRA-PAGO-ANTICIPADO`, `FRA-DEBIN-ENGANOSO`)

Principios de Reutilización y Seguridad:
- Reutiliza directamente los métodos de `TextAnalyzer` (`scripts/analyzer.py`) sin duplicar regex ni reglas.
- Opera sobre el texto preparado en `PreparationSessionContext` (`ctx.raw_active_text`).
- Verifica en código que todo fragmento devuelto exista literalmente en `ctx.raw_active_text`
  (rechaza o descarta cualquier evidencia que no pertenezca al texto analizado).
- Aplica `sanitize_snippets_for_external_llm` a los fragmentos que se devuelven al modelo externo
  para evitar fugas de PII en las respuestas de herramientas (`function_response`), conservando
  en memoria local los fragmentos verificados para el reporte final.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agents.common.contracts import (
    ContractValidationError,
    MessageSignalFinding,
    REQUIRED_MESSAGE_ANALYSIS_CATEGORIES,
    validate_tool_arguments,
)
from agents.common.privacy import sanitize_snippets_for_external_llm
from agents.tools.preparation_tools import PreparationSessionContext
from scripts.analyzer import TextAnalyzer
from scripts.worker import load_policy


@dataclass
class MessageAnalysisSessionState:
    """
    Estado aislado en memoria para la ejecución del Agente Analizador de Mensajes.
    Registra qué categorías fueron efectivamente revisadas, cuáles tuvieron hallazgos,
    cuáles no tuvieron hallazgos y si ocurrió algún error de herramienta.
    """
    categories_reviewed: List[str] = field(default_factory=list)
    category_status: Dict[str, str] = field(
        default_factory=lambda: {cat: "no_revisada" for cat in REQUIRED_MESSAGE_ANALYSIS_CATEGORIES}
    )
    findings_by_id: Dict[str, MessageSignalFinding] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    tools_called: List[str] = field(default_factory=list)
    tool_errors: List[str] = field(default_factory=list)

    def register_category_review(
        self,
        category_name: str,
        findings: List[MessageSignalFinding],
        analyzed_text: str,
    ) -> None:
        if category_name not in self.categories_reviewed:
            self.categories_reviewed.append(category_name)

        if findings:
            for f in findings:
                f.validate(analyzed_text=analyzed_text)
                if f.id_senal not in self.findings_by_id:
                    self.findings_by_id[f.id_senal] = f
                else:
                    existing = self.findings_by_id[f.id_senal]
                    for snip in f.evidence_snippets:
                        if snip not in existing.evidence_snippets:
                            existing.evidence_snippets.append(snip)
            self.category_status[category_name] = "revisada_con_hallazgos"
        else:
            # Si ya había sido revisada con hallazgos, mantener ese estado
            if self.category_status.get(category_name) != "revisada_con_hallazgos":
                self.category_status[category_name] = "revisada_sin_hallazgos"


def verify_snippets_in_text(snippets: List[str], analyzed_text: str, signal_id: str) -> List[str]:
    """
    Verifica en código que cada fragmento de evidencia pertenezca literalmente al texto analizado.
    Si algún fragmento no está en `analyzed_text`, lanza `ContractValidationError` para impedir
    evidencia inventada.
    """
    verified: List[str] = []
    for raw_snip in snippets or []:
        snip = str(raw_snip).strip()
        if not snip:
            continue
        if snip not in analyzed_text:
            raise ContractValidationError(
                f"Evidencia inventada o inexistente rechazada en '{signal_id}': "
                f"el fragmento '{snip[:80]}' no se encuentra en el texto analizado."
            )
        if snip not in verified:
            verified.append(snip)
    return verified


def _require_prepared_text(
    prep_ctx: PreparationSessionContext,
    msg_state: MessageAnalysisSessionState,
    tool_name: str,
) -> Optional[Dict[str, Any]]:
    """Verifica que exista texto preparado válido antes de ejecutar cualquier herramienta de análisis."""
    if not prep_ctx.raw_active_text or not prep_ctx.raw_active_text.strip():
        err_msg = (
            f"No hay texto preparado válido en la sesión para ejecutar '{tool_name}'. "
            f"Debe completarse la preparación con estado 'correcto' primero."
        )
        msg_state.tool_errors.append(err_msg)
        return {
            "status": "tool_error",
            "detected": False,
            "signals": [],
            "warnings": [],
            "error_message": err_msg,
        }
    return None


def execute_tool_detectar_urgencia(
    prep_ctx: PreparationSessionContext,
    msg_state: MessageAnalysisSessionState,
    raw_args: Optional[Dict[str, Any]] = None,
    analyzer_override: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Herramienta Python de la skill `detectar-urgencia`.
    Reutiliza `TextAnalyzer._detect_urgency`.
    """
    validate_tool_arguments(
        tool_name="tool_detectar_urgencia",
        args=raw_args,
        allowed_params={"confirm_session_text": bool},
        required_params=[],
    )
    msg_state.tools_called.append("tool_detectar_urgencia")

    err_out = _require_prepared_text(prep_ctx, msg_state, "tool_detectar_urgencia")
    if err_out is not None:
        return err_out

    text = prep_ctx.raw_active_text
    analyzer = analyzer_override or TextAnalyzer(load_policy())

    try:
        detected, raw_snippets = analyzer._detect_urgency(text)
        findings: List[MessageSignalFinding] = []
        masked_signals_for_llm: List[Dict[str, Any]] = []

        if detected and raw_snippets:
            verified_snippets = verify_snippets_in_text(
                raw_snippets, text, "ING-URGENCIA-ARTIFICIAL"
            )
            if verified_snippets:
                finding = MessageSignalFinding(
                    id_senal="ING-URGENCIA-ARTIFICIAL",
                    categoria_skill="urgencia",
                    categoria_motor="ingenieria_social",
                    severidad="MEDIA",
                    descripcion="Inducción deliberada de prisa temporal para forzar una decisión sin reflexión.",
                    fragmento_justificacion=verified_snippets[0],
                    evidence_snippets=verified_snippets,
                )
                findings.append(finding)
                safe_snips = sanitize_snippets_for_external_llm(verified_snippets)
                masked_signals_for_llm.append({
                    "id_senal": finding.id_senal,
                    "categoria": finding.categoria_skill,
                    "severidad": finding.severidad,
                    "fragmento_justificacion": safe_snips[0] if safe_snips else "",
                    "evidence_snippets": safe_snips,
                })

        msg_state.register_category_review("urgencia", findings, analyzed_text=text)
        return {
            "status": "ok",
            "category_reviewed": "urgencia",
            "category_status": msg_state.category_status["urgencia"],
            "detected": bool(findings),
            "signals": masked_signals_for_llm,
            "warnings": [],
            "error_message": None,
        }
    except ContractValidationError:
        raise
    except Exception as exc:
        err_msg = f"Fallo en tool_detectar_urgencia: {str(exc)}"
        msg_state.tool_errors.append(err_msg)
        return {
            "status": "tool_error",
            "category_reviewed": "urgencia",
            "detected": False,
            "signals": [],
            "warnings": [],
            "error_message": err_msg,
        }


def execute_tool_detectar_amenazas(
    prep_ctx: PreparationSessionContext,
    msg_state: MessageAnalysisSessionState,
    raw_args: Optional[Dict[str, Any]] = None,
    analyzer_override: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Herramienta Python de la skill `detectar-amenazas`.
    Reutiliza `TextAnalyzer._detect_blocking_threats`.
    """
    validate_tool_arguments(
        tool_name="tool_detectar_amenazas",
        args=raw_args,
        allowed_params={"confirm_session_text": bool},
        required_params=[],
    )
    msg_state.tools_called.append("tool_detectar_amenazas")

    err_out = _require_prepared_text(prep_ctx, msg_state, "tool_detectar_amenazas")
    if err_out is not None:
        return err_out

    text = prep_ctx.raw_active_text
    analyzer = analyzer_override or TextAnalyzer(load_policy())

    try:
        detected, raw_snippets = analyzer._detect_blocking_threats(text)
        findings: List[MessageSignalFinding] = []
        masked_signals_for_llm: List[Dict[str, Any]] = []

        if detected and raw_snippets:
            verified_snippets = verify_snippets_in_text(
                raw_snippets, text, "ING-AMENAZA-BLOQUEO"
            )
            if verified_snippets:
                finding = MessageSignalFinding(
                    id_senal="ING-AMENAZA-BLOQUEO",
                    categoria_skill="amenazas",
                    categoria_motor="ingenieria_social",
                    severidad="ALTA",
                    descripcion="Amenaza explícita de bloqueo, suspensión o consecuencias negativas sobre una cuenta o servicio.",
                    fragmento_justificacion=verified_snippets[0],
                    evidence_snippets=verified_snippets,
                )
                findings.append(finding)
                safe_snips = sanitize_snippets_for_external_llm(verified_snippets)
                masked_signals_for_llm.append({
                    "id_senal": finding.id_senal,
                    "categoria": finding.categoria_skill,
                    "severidad": finding.severidad,
                    "fragmento_justificacion": safe_snips[0] if safe_snips else "",
                    "evidence_snippets": safe_snips,
                })

        msg_state.register_category_review("amenazas", findings, analyzed_text=text)
        return {
            "status": "ok",
            "category_reviewed": "amenazas",
            "category_status": msg_state.category_status["amenazas"],
            "detected": bool(findings),
            "signals": masked_signals_for_llm,
            "warnings": [],
            "error_message": None,
        }
    except ContractValidationError:
        raise
    except Exception as exc:
        err_msg = f"Fallo en tool_detectar_amenazas: {str(exc)}"
        msg_state.tool_errors.append(err_msg)
        return {
            "status": "tool_error",
            "category_reviewed": "amenazas",
            "detected": False,
            "signals": [],
            "warnings": [],
            "error_message": err_msg,
        }


def execute_tool_detectar_premios(
    prep_ctx: PreparationSessionContext,
    msg_state: MessageAnalysisSessionState,
    raw_args: Optional[Dict[str, Any]] = None,
    analyzer_override: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Herramienta Python de la skill `detectar-premios`.
    Reutiliza `TextAnalyzer._detect_fake_rewards`.
    """
    validate_tool_arguments(
        tool_name="tool_detectar_premios",
        args=raw_args,
        allowed_params={"confirm_session_text": bool},
        required_params=[],
    )
    msg_state.tools_called.append("tool_detectar_premios")

    err_out = _require_prepared_text(prep_ctx, msg_state, "tool_detectar_premios")
    if err_out is not None:
        return err_out

    text = prep_ctx.raw_active_text
    analyzer = analyzer_override or TextAnalyzer(load_policy())

    try:
        detected, raw_snippets = analyzer._detect_fake_rewards(text)
        findings: List[MessageSignalFinding] = []
        masked_signals_for_llm: List[Dict[str, Any]] = []

        if detected and raw_snippets:
            verified_snippets = verify_snippets_in_text(
                raw_snippets, text, "FRA-PREMIO-INESPERADO"
            )
            if verified_snippets:
                finding = MessageSignalFinding(
                    id_senal="FRA-PREMIO-INESPERADO",
                    categoria_skill="premios",
                    categoria_motor="fraude_financiero",
                    severidad="ALTA",
                    descripcion="Promesa de premios no solicitados, sorteos no comprobables o bonos extraordinarios.",
                    fragmento_justificacion=verified_snippets[0],
                    evidence_snippets=verified_snippets,
                )
                findings.append(finding)
                safe_snips = sanitize_snippets_for_external_llm(verified_snippets)
                masked_signals_for_llm.append({
                    "id_senal": finding.id_senal,
                    "categoria": finding.categoria_skill,
                    "severidad": finding.severidad,
                    "fragmento_justificacion": safe_snips[0] if safe_snips else "",
                    "evidence_snippets": safe_snips,
                })

        msg_state.register_category_review("premios", findings, analyzed_text=text)
        return {
            "status": "ok",
            "category_reviewed": "premios",
            "category_status": msg_state.category_status["premios"],
            "detected": bool(findings),
            "signals": masked_signals_for_llm,
            "warnings": [],
            "error_message": None,
        }
    except ContractValidationError:
        raise
    except Exception as exc:
        err_msg = f"Fallo en tool_detectar_premios: {str(exc)}"
        msg_state.tool_errors.append(err_msg)
        return {
            "status": "tool_error",
            "category_reviewed": "premios",
            "detected": False,
            "signals": [],
            "warnings": [],
            "error_message": err_msg,
        }


def execute_tool_detectar_pedidos_datos(
    prep_ctx: PreparationSessionContext,
    msg_state: MessageAnalysisSessionState,
    raw_args: Optional[Dict[str, Any]] = None,
    analyzer_override: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Herramienta Python de la skill `detectar-pedidos-datos`.
    Reutiliza `TextAnalyzer._detect_credential_harvesting`.
    """
    validate_tool_arguments(
        tool_name="tool_detectar_pedidos_datos",
        args=raw_args,
        allowed_params={"confirm_session_text": bool},
        required_params=[],
    )
    msg_state.tools_called.append("tool_detectar_pedidos_datos")

    err_out = _require_prepared_text(prep_ctx, msg_state, "tool_detectar_pedidos_datos")
    if err_out is not None:
        return err_out

    text = prep_ctx.raw_active_text
    analyzer = analyzer_override or TextAnalyzer(load_policy())

    try:
        detected, raw_snippets = analyzer._detect_credential_harvesting(text)
        findings: List[MessageSignalFinding] = []
        masked_signals_for_llm: List[Dict[str, Any]] = []

        if detected and raw_snippets:
            verified_snippets = verify_snippets_in_text(
                raw_snippets, text, "FRA-CAPTURA-CREDENCIALES"
            )
            if verified_snippets:
                finding = MessageSignalFinding(
                    id_senal="FRA-CAPTURA-CREDENCIALES",
                    categoria_skill="pedidos_datos",
                    categoria_motor="captura_datos",
                    severidad="ALTA",
                    descripcion="Solicitud de datos confidenciales (contraseñas, tokens de seguridad, códigos de 6 dígitos o PIN).",
                    fragmento_justificacion=verified_snippets[0],
                    evidence_snippets=verified_snippets,
                )
                findings.append(finding)
                safe_snips = sanitize_snippets_for_external_llm(verified_snippets)
                masked_signals_for_llm.append({
                    "id_senal": finding.id_senal,
                    "categoria": finding.categoria_skill,
                    "severidad": finding.severidad,
                    "fragmento_justificacion": safe_snips[0] if safe_snips else "",
                    "evidence_snippets": safe_snips,
                })

        msg_state.register_category_review("pedidos_datos", findings, analyzed_text=text)
        return {
            "status": "ok",
            "category_reviewed": "pedidos_datos",
            "category_status": msg_state.category_status["pedidos_datos"],
            "detected": bool(findings),
            "signals": masked_signals_for_llm,
            "warnings": [],
            "error_message": None,
        }
    except ContractValidationError:
        raise
    except Exception as exc:
        err_msg = f"Fallo en tool_detectar_pedidos_datos: {str(exc)}"
        msg_state.tool_errors.append(err_msg)
        return {
            "status": "tool_error",
            "category_reviewed": "pedidos_datos",
            "detected": False,
            "signals": [],
            "warnings": [],
            "error_message": err_msg,
        }


def execute_tool_detectar_pedidos_dinero(
    prep_ctx: PreparationSessionContext,
    msg_state: MessageAnalysisSessionState,
    raw_args: Optional[Dict[str, Any]] = None,
    analyzer_override: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Herramienta Python de la skill `detectar-pedidos-dinero`.
    Reutiliza `TextAnalyzer._detect_advance_fee` (`FRA-PAGO-ANTICIPADO`) y
    `TextAnalyzer._detect_debin_trick` (`FRA-DEBIN-ENGANOSO`).
    """
    validate_tool_arguments(
        tool_name="tool_detectar_pedidos_dinero",
        args=raw_args,
        allowed_params={"confirm_session_text": bool},
        required_params=[],
    )
    msg_state.tools_called.append("tool_detectar_pedidos_dinero")

    err_out = _require_prepared_text(prep_ctx, msg_state, "tool_detectar_pedidos_dinero")
    if err_out is not None:
        return err_out

    text = prep_ctx.raw_active_text
    analyzer = analyzer_override or TextAnalyzer(load_policy())

    try:
        adv_detected, adv_snippets = analyzer._detect_advance_fee(text)
        debin_detected, debin_snippets = analyzer._detect_debin_trick(text)

        findings: List[MessageSignalFinding] = []
        masked_signals_for_llm: List[Dict[str, Any]] = []

        if adv_detected and adv_snippets:
            verified_adv = verify_snippets_in_text(
                adv_snippets, text, "FRA-PAGO-ANTICIPADO"
            )
            if verified_adv:
                f_adv = MessageSignalFinding(
                    id_senal="FRA-PAGO-ANTICIPADO",
                    categoria_skill="pedidos_dinero",
                    categoria_motor="fraude_financiero",
                    severidad="ALTA",
                    descripcion="Exigencia de abonar una tasa previa, seguro postal, o gasto administrativo para liberar un premio o paquete.",
                    fragmento_justificacion=verified_adv[0],
                    evidence_snippets=verified_adv,
                )
                findings.append(f_adv)
                safe_adv = sanitize_snippets_for_external_llm(verified_adv)
                masked_signals_for_llm.append({
                    "id_senal": f_adv.id_senal,
                    "categoria": f_adv.categoria_skill,
                    "severidad": f_adv.severidad,
                    "fragmento_justificacion": safe_adv[0] if safe_adv else "",
                    "evidence_snippets": safe_adv,
                })

        if debin_detected and debin_snippets:
            verified_debin = verify_snippets_in_text(
                debin_snippets, text, "FRA-DEBIN-ENGANOSO"
            )
            if verified_debin:
                f_debin = MessageSignalFinding(
                    id_senal="FRA-DEBIN-ENGANOSO",
                    categoria_skill="pedidos_dinero",
                    categoria_motor="fraude_financiero",
                    severidad="ALTA",
                    descripcion="Mención de DEBIN o transferencias por error orientadas a extraer fondos de la víctima.",
                    fragmento_justificacion=verified_debin[0],
                    evidence_snippets=verified_debin,
                )
                findings.append(f_debin)
                safe_debin = sanitize_snippets_for_external_llm(verified_debin)
                masked_signals_for_llm.append({
                    "id_senal": f_debin.id_senal,
                    "categoria": f_debin.categoria_skill,
                    "severidad": f_debin.severidad,
                    "fragmento_justificacion": safe_debin[0] if safe_debin else "",
                    "evidence_snippets": safe_debin,
                })

        msg_state.register_category_review("pedidos_dinero", findings, analyzed_text=text)
        return {
            "status": "ok",
            "category_reviewed": "pedidos_dinero",
            "category_status": msg_state.category_status["pedidos_dinero"],
            "detected": bool(findings),
            "signals": masked_signals_for_llm,
            "warnings": [],
            "error_message": None,
        }
    except ContractValidationError:
        raise
    except Exception as exc:
        err_msg = f"Fallo en tool_detectar_pedidos_dinero: {str(exc)}"
        msg_state.tool_errors.append(err_msg)
        return {
            "status": "tool_error",
            "category_reviewed": "pedidos_dinero",
            "detected": False,
            "signals": [],
            "warnings": [],
            "error_message": err_msg,
        }

