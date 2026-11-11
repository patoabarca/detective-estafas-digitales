"""
Agente Orquestador Real (`agents/orquestador/agent.py`).

Responsabilidad delimitada (Coordinador de Flujo):
- Recibe la solicitud desde la aplicación (`AgentInputRequest`) y valida su sobre.
- Inicializa `PreparationSessionContext`, `AgentTracer` y `OrchestrationSessionState`.
- Ejecuta el bucle real de herramientas (`run_agent_tool_loop`) exponiendo la lista
  cerrada de 4 herramientas de delegación (`delegation_tools.py`):
  `delegar_preparacion`, `delegar_analisis_mensaje`, `delegar_analisis_enlaces` y
  `delegar_evaluacion`.
- Delega la construcción de reportes seguros `INDETERMINADO` y la validación final de
  `OrchestratorResponse` en `result_builder.py`.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from agents.common.contracts import (
    AgentInputRequest,
    ContractValidationError,
    OrchestratorResponse,
)
from agents.common.llm_client import (
    AgentConfigurationError,
    AgentExecutionError,
    DEFAULT_GEMINI_MODEL,
    format_user_friendly_agent_error,
    run_agent_tool_loop,
)
from agents.common.privacy import SanitizationReport
from agents.common.traceability import AgentTracer
from agents.orquestador.delegation_tools import (
    OrchestrationSessionState,
    build_orquestador_allowed_tools,
)
from agents.orquestador.prompts import (
    ORQUESTADOR_AGENT_NAME,
    ORQUESTADOR_ALLOWED_TOOLS,
    ORQUESTADOR_SYSTEM_INSTRUCTIONS,
    ORQUESTADOR_TOOL_DECLARATIONS,
    build_orquestador_user_prompt,
)
from agents.orquestador.result_builder import (
    build_final_orchestrator_response,
    build_incomplete_message_analysis_report as _build_incomplete_message_analysis_report,
    build_incomplete_ocr_report as _build_incomplete_ocr_report,
    build_incomplete_url_analysis_report as _build_incomplete_url_analysis_report,
    build_omitted_url_analysis_result as _build_omitted_url_analysis_result,
)
from agents.tools.preparation_tools import PreparationSessionContext

# Re-exportación explícita de constantes para compatibilidad con pruebas y módulos externos
__all__ = [
    "ORQUESTADOR_AGENT_NAME",
    "ORQUESTADOR_ALLOWED_TOOLS",
    "ORQUESTADOR_SYSTEM_INSTRUCTIONS",
    "ORQUESTADOR_TOOL_DECLARATIONS",
    "OrquestadorAgent",
]


class OrquestadorAgent:
    """
    Agente Orquestador que coordina al Agente Preparador, al Agente Analizador de Mensajes,
    al Agente Analizador de Enlaces (cuando existen URLs) y al Agente Evaluador.
    """

    def __init__(
        self,
        orquestador_llm_client: Optional[Any] = None,
        preparador_llm_client: Optional[Any] = None,
        analizador_mensajes_llm_client: Optional[Any] = None,
        analizador_enlaces_llm_client: Optional[Any] = None,
        evaluador_llm_client: Optional[Any] = None,
        model_name: Optional[str] = None,
        ocr_service_override: Optional[Any] = None,
        analyzer_override: Optional[Any] = None,
        url_analyzer_override: Optional[Callable[[str], Dict[str, Any]]] = None,
        policy_override: Optional[Dict[str, Any]] = None,
        max_total_elapsed_seconds: float = 60.0,
    ) -> None:
        self.name = ORQUESTADOR_AGENT_NAME
        self.orquestador_llm_client = orquestador_llm_client
        self.preparador_llm_client = (
            preparador_llm_client if preparador_llm_client is not None else orquestador_llm_client
        )
        self.analizador_mensajes_llm_client = (
            analizador_mensajes_llm_client
            if analizador_mensajes_llm_client is not None
            else orquestador_llm_client
        )
        self.analizador_enlaces_llm_client = (
            analizador_enlaces_llm_client
            if analizador_enlaces_llm_client is not None
            else orquestador_llm_client
        )
        self.evaluador_llm_client = (
            evaluador_llm_client
            if evaluador_llm_client is not None
            else orquestador_llm_client
        )
        self.policy_override = policy_override
        self.model_name = model_name
        self.ocr_service_override = ocr_service_override
        self.analyzer_override = analyzer_override
        self.url_analyzer_override = url_analyzer_override
        self.max_total_elapsed_seconds = max_total_elapsed_seconds

    def build_system_instruction(self) -> str:
        """Devuelve la instrucción de sistema del Agente Orquestador."""
        return ORQUESTADOR_SYSTEM_INSTRUCTIONS

    def run(self, request: AgentInputRequest) -> OrchestratorResponse:
        """
        Ejecuta el recorrido completo:
        Streamlit -> Orquestador -> Preparador -> Analizador de Mensajes
        -> Analizador de Enlaces (si hay URLs) -> Evaluador.
        """
        tracer = AgentTracer()
        t0 = time.monotonic()

        try:
            request.validate_envelope()
        except ContractValidationError as env_err:
            tracer.record(
                agent=self.name,
                event_type="agent_error",
                tool="none",
                status="rejected",
                detail=f"Solicitud rechazada por contrato de entrada: {str(env_err)}",
            )
            return OrchestratorResponse(
                status="error",
                model_used=self.model_name or DEFAULT_GEMINI_MODEL,
                error_type="ContractValidationError",
                error_message=str(env_err),
                usage_metrics=tracer.get_usage_summary(),
                trace_events=tracer.get_events(),
            )

        session_ctx = PreparationSessionContext(
            input_mode=request.input_mode,
            raw_input_text=request.text_content,
            image_bytes=request.image_bytes,
            image_filename=request.image_filename,
            ocr_service_override=self.ocr_service_override,
        )

        orch_state = OrchestrationSessionState(
            session_ctx=session_ctx,
            tracer=tracer,
            started_monotonic=t0,
            max_total_elapsed_seconds=self.max_total_elapsed_seconds,
            preparador_llm_client=self.preparador_llm_client,
            analizador_mensajes_llm_client=self.analizador_mensajes_llm_client,
            analizador_enlaces_llm_client=self.analizador_enlaces_llm_client,
            evaluador_llm_client=self.evaluador_llm_client,
            model_name=self.model_name,
            analyzer_override=self.analyzer_override,
            url_analyzer_override=self.url_analyzer_override,
            policy_override=self.policy_override,
        )

        allowed_tools_map = build_orquestador_allowed_tools(orch_state)

        tracer.record(
            agent=self.name,
            event_type="agent_start",
            tool="none",
            status="ok",
            detail=f"Iniciando Agente Orquestador para solicitud en modo '{request.input_mode}'.",
        )

        user_prompt = build_orquestador_user_prompt(request.input_mode)

        try:
            loop_out = run_agent_tool_loop(
                agent_name=self.name,
                system_instruction=self.build_system_instruction(),
                user_prompt=user_prompt,
                allowed_tools=allowed_tools_map,
                tool_declarations=ORQUESTADOR_TOOL_DECLARATIONS,
                tracer=tracer,
                llm_client=self.orquestador_llm_client,
                model_name=self.model_name,
                max_tool_calls=7,
                max_elapsed_seconds=self.max_total_elapsed_seconds,
            )
        except (AgentConfigurationError, AgentExecutionError, ContractValidationError) as agent_err:
            privacy_info = (
                session_ctx.sanitization_report.to_dict()
                if session_ctx.sanitization_report
                else SanitizationReport(masked_text="").to_dict()
            )
            return OrchestratorResponse(
                status="error",
                model_used=self.model_name or DEFAULT_GEMINI_MODEL,
                preparation=orch_state.preparation,
                message_analysis=orch_state.message_analysis,
                url_analysis=orch_state.url_analysis,
                evaluation=orch_state.evaluation,
                report=None,
                privacy_notice=privacy_info,
                usage_metrics=tracer.get_usage_summary(),
                trace_events=tracer.get_events(),
                error_type=agent_err.__class__.__name__,
                error_message=format_user_friendly_agent_error(agent_err),
            )

        privacy_info = (
            session_ctx.sanitization_report.to_dict()
            if session_ctx.sanitization_report
            else SanitizationReport(masked_text="").to_dict()
        )
        elapsed_ms = (time.monotonic() - t0) * 1000

        return build_final_orchestrator_response(
            agent_name=self.name,
            tracer=tracer,
            loop_out=loop_out,
            prep_final=orch_state.preparation,
            msg_final=orch_state.message_analysis,
            url_final=orch_state.url_analysis,
            eval_final=orch_state.evaluation,
            privacy_info=privacy_info,
            elapsed_ms=elapsed_ms,
        )
