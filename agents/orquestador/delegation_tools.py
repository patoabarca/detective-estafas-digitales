"""
Herramientas de Delegación del Agente Orquestador (`agents/orquestador/delegation_tools.py`).

Responsabilidad delimitada:
- Mantener el estado de sesión aislado por solicitud (`OrchestrationSessionState`).
- Controlar el presupuesto de tiempo remanente entre especialistas.
- Implementar y validar las 4 herramientas cerradas del Orquestador:
  1. `execute_delegar_preparacion` -> `PreparadorAgent`
  2. `execute_delegar_analisis_mensaje` -> `AnalizadorMensajesAgent`
  3. `execute_delegar_analisis_enlaces` -> `AnalizadorEnlacesAgent` (condicional)
  4. `execute_delegar_evaluacion` -> `EvaluadorAgent`
- Sanitizar las vistas devueltas en `function_response` hacia el modelo externo.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable, Dict, Optional

from agents.analizador_enlaces.agent import AnalizadorEnlacesAgent
from agents.analizador_mensajes.agent import AnalizadorMensajesAgent
from agents.common.contracts import (
    ContractValidationError,
    EvaluationResult,
    MessageAnalysisResult,
    PreparationResult,
    UrlAnalysisResult,
    validate_tool_arguments,
)
from agents.common.llm_client import AgentExecutionError
from agents.common.privacy import (
    sanitize_text_for_external_llm,
    sanitize_url_for_external_llm,
)
from agents.common.traceability import AgentTracer
from agents.evaluador.agent import EvaluadorAgent
from agents.orquestador.result_builder import build_omitted_url_analysis_result
from agents.preparador.agent import PreparadorAgent
from agents.tools.preparation_tools import PreparationSessionContext


@dataclass
class OrchestrationSessionState:
    """Estado de ejecución en memoria aislado por solicitud para el Agente Orquestador."""

    session_ctx: PreparationSessionContext
    tracer: AgentTracer
    started_monotonic: float
    max_total_elapsed_seconds: float
    preparador_llm_client: Optional[Any] = None
    analizador_mensajes_llm_client: Optional[Any] = None
    analizador_enlaces_llm_client: Optional[Any] = None
    evaluador_llm_client: Optional[Any] = None
    model_name: Optional[str] = None
    analyzer_override: Optional[Any] = None
    url_analyzer_override: Optional[Callable[[str], Dict[str, Any]]] = None
    policy_override: Optional[Dict[str, Any]] = None
    preparation: Optional[PreparationResult] = None
    message_analysis: Optional[MessageAnalysisResult] = None
    url_analysis: Optional[UrlAnalysisResult] = None
    evaluation: Optional[EvaluationResult] = None

    def remaining_seconds(self, cap: float = 20.0) -> float:
        """Devuelve el saldo de tiempo disponible acotado por `cap` o lanza timeout."""
        remaining = self.max_total_elapsed_seconds - (time.monotonic() - self.started_monotonic)
        if remaining <= 0:
            raise AgentExecutionError(
                f"Se superó el presupuesto total de tiempo de la solicitud ({self.max_total_elapsed_seconds}s)."
            )
        return min(cap, remaining)


def execute_delegar_preparacion(
    orch_state: OrchestrationSessionState,
    raw_args: Dict[str, Any],
) -> Dict[str, Any]:
    """Paso 1: Delega validación, OCR y extracción de enlaces al `PreparadorAgent`."""
    validate_tool_arguments(
        tool_name="delegar_preparacion",
        args=raw_args,
        allowed_params={"input_mode": str},
        required_params=["input_mode"],
    )
    rem_sec = orch_state.remaining_seconds(cap=20.0)
    preparador = PreparadorAgent(
        llm_client=orch_state.preparador_llm_client,
        model_name=orch_state.model_name,
    )
    prep_res = preparador.run(
        session_ctx=orch_state.session_ctx,
        tracer=orch_state.tracer,
        max_elapsed_seconds=rem_sec,
    )
    orch_state.preparation = prep_res

    if prep_res.estado == "correcto" and len(prep_res.enlaces_encontrados) == 0:
        orch_state.url_analysis = build_omitted_url_analysis_result()
        orch_state.tracer.record(
            agent="orquestador",
            event_type="agent_skipped",
            tool="delegar_analisis_enlaces",
            status="ok",
            detail=(
                "Sin enlaces en el mensaje preparado (sin_enlaces): se omite "
                "la llamada al Agente Analizador de Enlaces."
            ),
        )

    masked_preview = (
        orch_state.session_ctx.masked_active_text[:500]
        if orch_state.session_ctx.masked_active_text
        else ""
    )
    safe_urls_for_llm = [
        sanitize_url_for_external_llm(u)[0] for u in prep_res.enlaces_encontrados
    ]
    return {
        "status": "ok" if prep_res.estado == "correcto" else prep_res.estado,
        "estado": prep_res.estado,
        "detalle_estado": prep_res.detalle_estado,
        "modalidad_entrada": prep_res.modalidad_entrada,
        "char_count": len(prep_res.texto_extraido_o_recibido),
        "masked_text_preview": masked_preview,
        "links_count": len(prep_res.enlaces_encontrados),
        "url_ids": list(orch_state.session_ctx.url_id_map.keys()),
        "enlaces_encontrados": safe_urls_for_llm,
        "advertencias": prep_res.advertencias,
        "mensaje_error": prep_res.mensaje_error,
    }


def execute_delegar_analisis_mensaje(
    orch_state: OrchestrationSessionState,
    raw_args: Dict[str, Any],
) -> Dict[str, Any]:
    """Paso 2: Delega el análisis de las 5 categorías al `AnalizadorMensajesAgent`."""
    validated = validate_tool_arguments(
        tool_name="delegar_analisis_mensaje",
        args=raw_args,
        allowed_params={"confirm_prepared": bool},
        required_params=["confirm_prepared"],
    )
    if not validated.get("confirm_prepared"):
        raise ContractValidationError(
            "El parámetro 'confirm_prepared' debe ser True para delegar el análisis del mensaje."
        )

    prep_res = orch_state.preparation
    if prep_res is None or prep_res.estado != "correcto":
        return {
            "status": "rejected",
            "error_message": (
                "No se puede delegar el análisis del mensaje porque la preparación no finalizó "
                "en estado 'correcto'."
            ),
        }

    rem_sec = orch_state.remaining_seconds(cap=20.0)
    analizador = AnalizadorMensajesAgent(
        llm_client=orch_state.analizador_mensajes_llm_client,
        model_name=orch_state.model_name,
        analyzer_override=orch_state.analyzer_override,
    )
    msg_res = analizador.run(
        session_ctx=orch_state.session_ctx,
        tracer=orch_state.tracer,
        max_elapsed_seconds=rem_sec,
    )
    orch_state.message_analysis = msg_res

    safe_signals_summary = [
        {
            "id_senal": s.id_senal,
            "categoria": s.categoria_skill,
            "severidad": s.severidad,
            "fragmento_justificacion": sanitize_text_for_external_llm(
                s.fragmento_justificacion
            ).masked_text,
        }
        for s in msg_res.senales_encontradas
    ]
    return {
        "status": "ok" if msg_res.estado == "correcto" else msg_res.estado,
        "estado": msg_res.estado,
        "categorias_revisadas": msg_res.categorias_revisadas,
        "categorias_sin_hallazgos": msg_res.categorias_sin_hallazgos,
        "categorias_no_revisadas": msg_res.categorias_no_revisadas,
        "estado_categorias": msg_res.estado_categorias,
        "senales_encontradas": safe_signals_summary,
        "links_pending_analysis": len(prep_res.enlaces_encontrados),
        "advertencias": msg_res.advertencias,
        "mensaje_error": msg_res.mensaje_error,
    }


def execute_delegar_analisis_enlaces(
    orch_state: OrchestrationSessionState,
    raw_args: Dict[str, Any],
) -> Dict[str, Any]:
    """Paso 3 (condicional): Delega la auditoría estática de URLs al `AnalizadorEnlacesAgent`."""
    validated = validate_tool_arguments(
        tool_name="delegar_analisis_enlaces",
        args=raw_args,
        allowed_params={"confirm_links_present": bool},
        required_params=["confirm_links_present"],
    )
    if not validated.get("confirm_links_present"):
        raise ContractValidationError(
            "El parámetro 'confirm_links_present' debe ser True para delegar el análisis de enlaces."
        )

    prep_res = orch_state.preparation
    if prep_res is None or prep_res.estado != "correcto":
        return {
            "status": "rejected",
            "error_message": (
                "No se puede delegar el análisis de enlaces porque la preparación no finalizó "
                "en estado 'correcto'."
            ),
        }

    msg_res = orch_state.message_analysis
    if msg_res is None or msg_res.estado != "correcto":
        return {
            "status": "rejected",
            "error_message": (
                "Orden de ejecución inválido: debe completarse 'delegar_analisis_mensaje' con "
                "estado 'correcto' antes de 'delegar_analisis_enlaces'."
            ),
        }

    if len(prep_res.enlaces_encontrados) == 0:
        omitted_res = build_omitted_url_analysis_result()
        orch_state.url_analysis = omitted_res
        return {
            "status": "skipped_no_links",
            "estado": "correcto",
            "detalle_estado": "sin_enlaces",
            "intervino_agente": False,
            "motivo_omision": omitted_res.motivo_omision,
            "cantidad_enlaces_procesados": 0,
        }

    rem_sec = orch_state.remaining_seconds(cap=20.0)
    analizador_url = AnalizadorEnlacesAgent(
        llm_client=orch_state.analizador_enlaces_llm_client,
        model_name=orch_state.model_name,
        url_analyzer_override=orch_state.url_analyzer_override,
    )
    url_res = analizador_url.run(
        session_ctx=orch_state.session_ctx,
        tracer=orch_state.tracer,
        max_elapsed_seconds=rem_sec,
    )
    orch_state.url_analysis = url_res
    prep_res.url_details = url_res.to_engine_url_analyses()

    safe_links_summary = [
        {
            "url_id": it.url_id,
            "masked_url": it.masked_url,
            "estado_enlace": it.estado_enlace,
            "reglas_activadas": list(it.reglas_activadas),
            "cantidad_senales": len(it.senales_encontradas),
        }
        for it in url_res.enlaces_analizados
    ]
    return {
        "status": "ok" if url_res.estado == "correcto" else url_res.estado,
        "estado": url_res.estado,
        "detalle_estado": url_res.detalle_estado,
        "intervino_agente": url_res.intervino_agente,
        "cantidad_enlaces_extraidos": url_res.cantidad_enlaces_extraidos,
        "cantidad_enlaces_procesados": url_res.cantidad_enlaces_procesados,
        "enlaces_analizados": safe_links_summary,
        "enlaces_omitidos": url_res.enlaces_omitidos,
        "advertencias": [
            sanitize_text_for_external_llm(w).masked_text for w in url_res.advertencias
        ],
        "mensaje_error": url_res.mensaje_error,
    }


def execute_delegar_evaluacion(
    orch_state: OrchestrationSessionState,
    raw_args: Dict[str, Any],
) -> Dict[str, Any]:
    """Paso 4: Verifica precondiciones y delega la evaluación final al `EvaluadorAgent`."""
    validated = validate_tool_arguments(
        tool_name="delegar_evaluacion",
        args=raw_args,
        allowed_params={
            "confirm_analyses_completed": bool,
            "generate_pdf": bool,
        },
        required_params=["confirm_analyses_completed"],
    )
    if not validated.get("confirm_analyses_completed"):
        raise ContractValidationError(
            "El parámetro 'confirm_analyses_completed' debe ser True para delegar la evaluación."
        )
    generate_pdf = bool(validated.get("generate_pdf", False))
    orch_state.remaining_seconds()

    prep_res = orch_state.preparation
    if prep_res is None or prep_res.estado != "correcto":
        return {
            "status": "rejected",
            "error_message": (
                "No se puede delegar la evaluación porque la preparación no finalizó "
                "en estado 'correcto'."
            ),
        }

    msg_res = orch_state.message_analysis
    if msg_res is None:
        return {
            "status": "rejected",
            "error_message": (
                "Orden de ejecución inválido: debe invocarse 'delegar_analisis_mensaje' antes de "
                "'delegar_evaluacion'."
            ),
        }
    if msg_res.estado != "correcto":
        return {
            "status": "rejected",
            "error_message": (
                f"No se puede delegar la evaluación porque el análisis del mensaje "
                f"finalizó en estado '{msg_res.estado}'."
            ),
        }

    has_extracted_links = len(prep_res.enlaces_encontrados) > 0
    url_res = orch_state.url_analysis

    if has_extracted_links:
        if url_res is None or not url_res.intervino_agente:
            return {
                "status": "rejected",
                "error_message": (
                    "Orden de ejecución inválido: existen enlaces en el mensaje preparado y debe "
                    "invocarse 'delegar_analisis_enlaces' antes de 'delegar_evaluacion'."
                ),
            }
        if url_res.estado != "correcto":
            return {
                "status": "rejected",
                "error_message": (
                    f"No se puede delegar la evaluación porque el análisis de enlaces "
                    f"finalizó en estado '{url_res.estado}' ({url_res.detalle_estado})."
                ),
            }
    else:
        if url_res is None:
            url_res = build_omitted_url_analysis_result()
            orch_state.url_analysis = url_res

    rem_sec = orch_state.remaining_seconds(cap=20.0)
    evaluador = EvaluadorAgent(
        llm_client=orch_state.evaluador_llm_client,
        model_name=orch_state.model_name,
        policy_override=orch_state.policy_override,
        analyzer_override=orch_state.analyzer_override,
    )
    eval_res = evaluador.run(
        session_ctx=orch_state.session_ctx,
        prep_res=prep_res,
        msg_res=msg_res,
        url_res=url_res,
        tracer=orch_state.tracer,
        generate_pdf=generate_pdf,
        max_elapsed_seconds=rem_sec,
    )
    orch_state.evaluation = eval_res
    return {
        "status": "ok" if eval_res.estado == "correcto" else eval_res.estado,
        "nivel_riesgo": eval_res.nivel_riesgo,
        "score": eval_res.puntaje,
        "resumen": eval_res.resumen,
        "activated_rules": eval_res.reglas_activadas,
        "recommendations_count": len(eval_res.recomendaciones),
        "pdf_generado": eval_res.pdf_generado,
    }


def build_orquestador_allowed_tools(
    orch_state: OrchestrationSessionState,
) -> Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]:
    """Construye la lista cerrada de herramientas ejecutables del Orquestador."""
    return {
        "delegar_preparacion": lambda args: execute_delegar_preparacion(orch_state, args),
        "delegar_analisis_mensaje": lambda args: execute_delegar_analisis_mensaje(orch_state, args),
        "delegar_analisis_enlaces": lambda args: execute_delegar_analisis_enlaces(orch_state, args),
        "delegar_evaluacion": lambda args: execute_delegar_evaluacion(orch_state, args),
    }
