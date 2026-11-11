"""
Construcción de Reportes Seguros y Respuestas Validadas del Agente Orquestador.

Responsabilidad delimitada:
- Construir `UrlAnalysisResult` de omisión justificada cuando el mensaje no contiene enlaces.
- Construir reportes seguros `INDETERMINADO` cuando la preparación OCR, el análisis de
  mensaje o el análisis de enlaces finalizan en estado `incompleto` (nunca `BAJO`).
- Consolidar y validar el contrato `OrchestratorResponse` final en todos los desenlaces
  (éxito, incompleto o error).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents.common.contracts import (
    EvaluationResult,
    MessageAnalysisResult,
    OrchestratorResponse,
    PreparationResult,
    UrlAnalysisResult,
)
from agents.common.llm_client import DEFAULT_GEMINI_MODEL
from agents.common.traceability import AgentTracer


def build_omitted_url_analysis_result() -> UrlAnalysisResult:
    """
    Construye el resultado estructurado cuando el mensaje preparado no contiene enlaces,
    documentando explícitamente el motivo de omisión sin tratarlo como un error.
    """
    res = UrlAnalysisResult(
        estado="correcto",
        detalle_estado="sin_enlaces",
        intervino_agente=False,
        motivo_omision=(
            "No se detectaron enlaces en el mensaje preparado (detalle_estado='sin_enlaces'); "
            "se omitió la invocación al Agente Analizador de Enlaces."
        ),
        cantidad_enlaces_extraidos=0,
        cantidad_enlaces_procesados=0,
        enlaces_analizados=[],
        enlaces_omitidos=[],
        advertencias=[],
        mensaje_error=None,
        skills_cargadas=[],
        herramientas_invocadas=[],
    )
    res.validate(expected_urls=[])
    return res


def _make_indeterminate_report_envelope(
    input_mode: str,
    input_char_count: int,
    summary: str,
    activated_rule: str,
    indicators_detected: List[Dict[str, Any]],
    url_analysis: List[Dict[str, Any]],
    limitations: List[str],
    recommendations: List[str],
    explanation: str,
) -> Dict[str, Any]:
    """Construye la estructura común de reporte seguro con nivel INDETERMINADO."""
    return {
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_mode": input_mode,
        "input_char_count": input_char_count,
        "risk_assessment": {
            "level": "INDETERMINADO",
            "score": 0,
            "score_type": "heuristic_severity_score",
            "score_disclaimer": (
                "Puntaje heurístico acumulativo (0-100). No representa una probabilidad estadística de fraude."
            ),
            "summary": summary,
            "activated_rules": [activated_rule],
        },
        "indicators_detected": indicators_detected,
        "url_analysis": url_analysis,
        "prompt_injection_detected": False,
        "prompt_injection_details": [],
        "limitations": limitations,
        "recommendations": recommendations,
        "non_technical_explanation": explanation,
    }


def build_incomplete_ocr_report(prep: PreparationResult) -> Dict[str, Any]:
    """Construye reporte seguro INDETERMINADO cuando una captura es ilegible."""
    return _make_indeterminate_report_envelope(
        input_mode=prep.modalidad_entrada,
        input_char_count=0,
        summary=(
            "No fue posible extraer texto legible de la captura suministrada. "
            "Una imagen ilegible o sin texto no puede clasificarse como segura (Riesgo Bajo)."
        ),
        activated_rule="REGLA-INDET-OCR (0 pts): Captura de pantalla sin texto legible extraído por OCR.",
        indicators_detected=[],
        url_analysis=[],
        limitations=[
            "El análisis requiere texto legible; la imagen proporcionada no produjo caracteres reconocibles mediante OCR local.",
            "La imposibilidad de leer la imagen NO implica que el mensaje sea seguro o legítimo.",
        ],
        recommendations=[
            "Intentá subir una captura con mayor nitidez y contraste, o transcribí manualmente el texto del mensaje.",
            "No hagas clic en enlaces ni compartas claves o códigos hasta poder verificar el contenido.",
        ],
        explanation=(
            "No pudimos leer el texto de la imagen porque la captura está en blanco, borrosa o no contiene "
            "letras reconocibles. Por tu seguridad, nunca clasificamos una imagen ilegible como 'Riesgo Bajo'. "
            "Podés escribir el texto manualmente en el recuadro para analizarlo."
        ),
    )


def build_incomplete_message_analysis_report(
    prep: PreparationResult,
    msg_analysis: MessageAnalysisResult,
) -> Dict[str, Any]:
    """Construye reporte seguro INDETERMINADO cuando faltaron categorías de mensaje."""
    missing_str = ", ".join(msg_analysis.categorias_no_revisadas)
    return _make_indeterminate_report_envelope(
        input_mode=prep.modalidad_entrada,
        input_char_count=len(prep.texto_extraido_o_recibido),
        summary=(
            f"El análisis del mensaje quedó incompleto porque faltaron revisar categorías obligatorias "
            f"({missing_str}). Por seguridad, un análisis parcial no se clasifica como Riesgo Bajo."
        ),
        activated_rule=f"REGLA-INDET-ANALISIS (0 pts): Categorías obligatorias no revisadas ({missing_str}).",
        indicators_detected=msg_analysis.to_engine_indicators(),
        url_analysis=prep.url_details,
        limitations=[
            f"Faltó completar la revisión de las siguientes categorías: {missing_str}.",
            "Un análisis incompleto no garantiza ausencia de señales de fraude.",
        ],
        recommendations=[
            "Volvé a ejecutar el análisis o utilizá el Modo Local Determinístico para obtener la revisión completa.",
            "Evitá hacer clic en enlaces o compartir datos sensibles.",
        ],
        explanation=(
            f"El agente analizador de mensajes no completó la revisión de todas las categorías obligatorias "
            f"(faltó revisar: {missing_str}). Por precaución clasificamos el resultado como INDETERMINADO."
        ),
    )


def build_incomplete_url_analysis_report(
    prep: PreparationResult,
    msg_analysis: MessageAnalysisResult,
    url_analysis: UrlAnalysisResult,
) -> Dict[str, Any]:
    """Construye reporte seguro INDETERMINADO cuando falló o quedó incompleto el análisis de URLs."""
    reason_detail = (
        url_analysis.mensaje_error
        or f"El análisis de enlaces finalizó con detalle '{url_analysis.detalle_estado}'."
    )
    return _make_indeterminate_report_envelope(
        input_mode=prep.modalidad_entrada,
        input_char_count=len(prep.texto_extraido_o_recibido),
        summary=(
            f"El análisis estructural de enlaces quedó incompleto ({url_analysis.detalle_estado}). "
            f"Por seguridad, un mensaje con enlaces omitidos o no analizables no se clasifica como Riesgo Bajo."
        ),
        activated_rule=f"REGLA-INDET-URL (0 pts): Análisis de enlaces incompleto ({url_analysis.detalle_estado}).",
        indicators_detected=msg_analysis.to_engine_indicators(),
        url_analysis=url_analysis.to_engine_url_analyses(),
        limitations=[
            reason_detail,
            "Un enlace que no pudo analizarse o fue omitido nunca debe considerarse seguro.",
        ],
        recommendations=[
            "No abras ni visites el enlace sospechoso o malformado.",
            "Podés verificar el mensaje con el Modo Local Determinístico o consultar a la entidad por sus canales oficiales.",
        ],
        explanation=(
            f"No fue posible completar el análisis de todos los enlaces del mensaje ({reason_detail}). "
            "Por precaución, clasificamos el resultado como INDETERMINADO y te recomendamos no abrir esos enlaces."
        ),
    )


def _attach_orchestration_metadata(
    report: Dict[str, Any],
    model_used: str,
    prep_final: PreparationResult,
    msg_final: Optional[MessageAnalysisResult],
    url_final: Optional[UrlAnalysisResult],
    eval_final: Optional[EvaluationResult],
    privacy_info: Dict[str, Any],
    tracer: AgentTracer,
    orchestrator_summary: Optional[str] = None,
) -> None:
    """Adjunta el bloque homogéneo `agent_orchestration` al diccionario del reporte."""
    meta: Dict[str, Any] = {
        "execution_mode": "agent_orchestrated",
        "model_used": model_used,
    }
    if orchestrator_summary is not None:
        meta["orchestrator_summary"] = orchestrator_summary
    meta.update(
        {
            "preparation": prep_final.to_dict(),
            "message_analysis": msg_final.to_dict() if msg_final else None,
            "url_analysis": url_final.to_dict() if url_final else None,
        }
    )
    if eval_final is not None:
        meta["evaluation"] = eval_final.to_dict()
    meta.update(
        {
            "privacy_notice": privacy_info,
            "usage_metrics": tracer.get_usage_summary(),
            "trace_events": tracer.get_events(),
        }
    )
    report["agent_orchestration"] = meta


def _record_error_and_build_response(
    agent_name: str,
    tracer: AgentTracer,
    event_type: str,
    tool: str,
    detail: str,
    elapsed_ms: float,
    model_used: str,
    error_type: str,
    error_message: str,
    privacy_info: Dict[str, Any],
    prep_final: Optional[PreparationResult] = None,
    msg_final: Optional[MessageAnalysisResult] = None,
    url_final: Optional[UrlAnalysisResult] = None,
    orchestrator_summary: str = "",
    validate_response: bool = False,
) -> OrchestratorResponse:
    """Registra la traza de error y devuelve un `OrchestratorResponse` de error."""
    tracer.record(
        agent=agent_name,
        event_type=event_type,
        tool=tool,
        status="error",
        detail=detail,
        duration_ms=elapsed_ms,
    )
    resp = OrchestratorResponse(
        status="error",
        model_used=model_used,
        preparation=prep_final,
        message_analysis=msg_final,
        url_analysis=url_final,
        report=None,
        orchestrator_summary=orchestrator_summary,
        privacy_notice=privacy_info,
        usage_metrics=tracer.get_usage_summary(),
        trace_events=tracer.get_events(),
        error_type=error_type,
        error_message=error_message,
    )
    if validate_response:
        resp.validate()
    return resp


def _record_incomplete_and_build_response(
    agent_name: str,
    tracer: AgentTracer,
    detail: str,
    elapsed_ms: float,
    model_used: str,
    report: Dict[str, Any],
    prep_final: PreparationResult,
    msg_final: Optional[MessageAnalysisResult],
    url_final: Optional[UrlAnalysisResult],
    orchestrator_summary: str,
    privacy_info: Dict[str, Any],
) -> OrchestratorResponse:
    """Registra traza incompleta, adjunta metadata y valida `OrchestratorResponse`."""
    _attach_orchestration_metadata(
        report=report,
        model_used=model_used,
        prep_final=prep_final,
        msg_final=msg_final,
        url_final=url_final,
        eval_final=None,
        privacy_info=privacy_info,
        tracer=tracer,
    )
    tracer.record(
        agent=agent_name,
        event_type="agent_finish",
        tool="none",
        status="incomplete",
        detail=detail,
        duration_ms=elapsed_ms,
    )
    resp = OrchestratorResponse(
        status="incomplete",
        model_used=model_used,
        preparation=prep_final,
        message_analysis=msg_final,
        url_analysis=url_final,
        report=report,
        orchestrator_summary=orchestrator_summary,
        privacy_notice=privacy_info,
        usage_metrics=tracer.get_usage_summary(),
        trace_events=tracer.get_events(),
    )
    resp.validate()
    return resp


def build_final_orchestrator_response(
    agent_name: str,
    tracer: AgentTracer,
    loop_out: Dict[str, Any],
    prep_final: Optional[PreparationResult],
    msg_final: Optional[MessageAnalysisResult],
    url_final: Optional[UrlAnalysisResult],
    eval_final: Optional[EvaluationResult],
    privacy_info: Dict[str, Any],
    elapsed_ms: float,
) -> OrchestratorResponse:
    """
    Evalúa los resultados acumulados de la orquestación y construye la respuesta
    validada final (`OrchestratorResponse`).
    """
    model_used = loop_out.get("model_used", DEFAULT_GEMINI_MODEL)
    summary_text = loop_out.get("final_text", "")

    if prep_final is None:
        return _record_error_and_build_response(
            agent_name=agent_name,
            tracer=tracer,
            event_type="agent_error",
            tool="none",
            detail="El Agente Orquestador finalizó sin delegar la preparación.",
            elapsed_ms=elapsed_ms,
            model_used=model_used,
            error_type="OrchestrationIncompleteError",
            error_message="El Agente Orquestador no invocó la delegación al Agente Preparador.",
            privacy_info=privacy_info,
        )

    if prep_final.estado == "error":
        return _record_error_and_build_response(
            agent_name=agent_name,
            tracer=tracer,
            event_type="agent_finish",
            tool="none",
            detail=f"Orquestación detenida por preparación en estado='error' ({prep_final.detalle_estado}).",
            elapsed_ms=elapsed_ms,
            model_used=model_used,
            error_type=prep_final.detalle_estado,
            error_message=prep_final.mensaje_error or "Error durante la etapa de preparación.",
            privacy_info=privacy_info,
            prep_final=prep_final,
            orchestrator_summary=summary_text,
            validate_response=True,
        )

    if prep_final.estado == "incompleto":
        return _record_incomplete_and_build_response(
            agent_name=agent_name,
            tracer=tracer,
            detail="Orquestación finalizada con estado='incompleto' (evaluación INDETERMINADO, nunca BAJO).",
            elapsed_ms=elapsed_ms,
            model_used=model_used,
            report=build_incomplete_ocr_report(prep_final),
            prep_final=prep_final,
            msg_final=None,
            url_final=None,
            orchestrator_summary=summary_text,
            privacy_info=privacy_info,
        )

    if msg_final is None:
        return _record_error_and_build_response(
            agent_name=agent_name,
            tracer=tracer,
            event_type="agent_error",
            tool="delegar_analisis_mensaje",
            detail="El Orquestador no invocó 'delegar_analisis_mensaje' tras una preparación exitosa.",
            elapsed_ms=elapsed_ms,
            model_used=model_used,
            error_type="MissingMessageAnalysisCall",
            error_message="El Agente Orquestador completó la preparación pero no delegó el análisis del mensaje.",
            privacy_info=privacy_info,
            prep_final=prep_final,
            url_final=url_final,
        )

    if msg_final.estado == "error":
        return _record_error_and_build_response(
            agent_name=agent_name,
            tracer=tracer,
            event_type="agent_finish",
            tool="none",
            detail="Orquestación detenida por error en el Agente Analizador de Mensajes.",
            elapsed_ms=elapsed_ms,
            model_used=model_used,
            error_type="MessageAnalysisToolError",
            error_message=msg_final.mensaje_error or "Fallo en una herramienta del Agente Analizador de Mensajes.",
            privacy_info=privacy_info,
            prep_final=prep_final,
            msg_final=msg_final,
            url_final=url_final,
            orchestrator_summary=summary_text,
            validate_response=True,
        )

    if msg_final.estado == "incompleto":
        return _record_incomplete_and_build_response(
            agent_name=agent_name,
            tracer=tracer,
            detail="Orquestación finalizada con estado='incompleto' por categorías faltantes en Analizador de Mensajes.",
            elapsed_ms=elapsed_ms,
            model_used=model_used,
            report=build_incomplete_message_analysis_report(prep_final, msg_final),
            prep_final=prep_final,
            msg_final=msg_final,
            url_final=url_final,
            orchestrator_summary=summary_text,
            privacy_info=privacy_info,
        )

    if len(prep_final.enlaces_encontrados) > 0:
        if url_final is None or not url_final.intervino_agente:
            return _record_error_and_build_response(
                agent_name=agent_name,
                tracer=tracer,
                event_type="agent_error",
                tool="delegar_analisis_enlaces",
                detail="El Orquestador no invocó 'delegar_analisis_enlaces' habiendo enlaces extraídos.",
                elapsed_ms=elapsed_ms,
                model_used=model_used,
                error_type="MissingUrlAnalysisCall",
                error_message=(
                    "El Agente Orquestador detectó enlaces en la preparación pero no delegó su análisis "
                    "al Agente Analizador de Enlaces."
                ),
                privacy_info=privacy_info,
                prep_final=prep_final,
                msg_final=msg_final,
            )

        if url_final.estado == "error":
            return _record_error_and_build_response(
                agent_name=agent_name,
                tracer=tracer,
                event_type="agent_finish",
                tool="none",
                detail="Orquestación detenida por error en el Agente Analizador de Enlaces.",
                elapsed_ms=elapsed_ms,
                model_used=model_used,
                error_type="UrlAnalysisToolError",
                error_message=(
                    url_final.mensaje_error
                    or "Fallo técnico en la herramienta del Agente Analizador de Enlaces."
                ),
                privacy_info=privacy_info,
                prep_final=prep_final,
                msg_final=msg_final,
                url_final=url_final,
                orchestrator_summary=summary_text,
                validate_response=True,
            )

        if url_final.estado == "incompleto":
            return _record_incomplete_and_build_response(
                agent_name=agent_name,
                tracer=tracer,
                detail=(
                    f"Orquestación finalizada con estado='incompleto' por análisis de enlaces "
                    f"({url_final.detalle_estado})."
                ),
                elapsed_ms=elapsed_ms,
                model_used=model_used,
                report=build_incomplete_url_analysis_report(prep_final, msg_final, url_final),
                prep_final=prep_final,
                msg_final=msg_final,
                url_final=url_final,
                orchestrator_summary=summary_text,
                privacy_info=privacy_info,
            )
    else:
        if url_final is None:
            url_final = build_omitted_url_analysis_result()

    if eval_final is None:
        return _record_error_and_build_response(
            agent_name=agent_name,
            tracer=tracer,
            event_type="agent_error",
            tool="delegar_evaluacion",
            detail="El Orquestador no invocó 'delegar_evaluacion' tras completar los análisis.",
            elapsed_ms=elapsed_ms,
            model_used=model_used,
            error_type="MissingEvaluationCall",
            error_message="El Agente Orquestador completó los análisis pero no delegó la evaluación al Agente Evaluador.",
            privacy_info=privacy_info,
            prep_final=prep_final,
            msg_final=msg_final,
            url_final=url_final,
        )

    final_report = eval_final.to_engine_report(
        input_char_count=len(prep_final.texto_extraido_o_recibido),
        input_mode=prep_final.modalidad_entrada,
    )
    final_report["input_char_count"] = len(prep_final.texto_extraido_o_recibido)
    final_report["input_mode"] = prep_final.modalidad_entrada

    tracer.record(
        agent=agent_name,
        event_type="agent_finish",
        tool="none",
        status="ok" if eval_final.estado == "correcto" else "incomplete",
        detail=(
            "Orquestador completó preparación, análisis de mensaje, "
            f"{'análisis de enlaces' if url_final.intervino_agente else 'omisión justificada de enlaces'} "
            f"y evaluación final (estado='{eval_final.estado}', nivel='{eval_final.nivel_riesgo}')."
        ),
        duration_ms=elapsed_ms,
    )

    _attach_orchestration_metadata(
        report=final_report,
        model_used=model_used,
        prep_final=prep_final,
        msg_final=msg_final,
        url_final=url_final,
        eval_final=eval_final,
        privacy_info=privacy_info,
        tracer=tracer,
        orchestrator_summary=summary_text,
    )

    resp = OrchestratorResponse(
        status="success" if eval_final.estado == "correcto" else "incomplete",
        model_used=model_used,
        preparation=prep_final,
        message_analysis=msg_final,
        url_analysis=url_final,
        evaluation=eval_final,
        report=final_report,
        orchestrator_summary=summary_text,
        privacy_notice=privacy_info,
        usage_metrics=tracer.get_usage_summary(),
        trace_events=tracer.get_events(),
    )
    resp.validate()
    return resp
