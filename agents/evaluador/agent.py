"""
Agente Evaluador (Etapa 4) (`agents/evaluador/agent.py`).

Responsabilidad delimitada (Coordinador):
- Carga dinámicamente sus 6 skills autorizadas (`reunir-hallazgos`, `calcular-puntaje`,
  `asignar-nivel-riesgo`, `explicar-resultado`, `recomendar-cuidados`, `generar-pdf`).
- Ensambla las instrucciones de sistema combinando la base y las skills cargadas.
- Ejecuta el bucle de herramientas (`run_agent_tool_loop`) inyectando el mapa explícito
  de prioridades `EVALUADOR_TOOL_ORDER_PRIORITY`.
- Registra eventos de trazabilidad en `AgentTracer`.
- Delega la construcción y validación estricta de `EvaluationResult` en `result_builder.py`.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from agents.common.contracts import (
    EvaluationResult,
    MessageAnalysisResult,
    PreparationResult,
    UrlAnalysisResult,
)
from agents.common.llm_client import DEFAULT_GEMINI_MODEL, run_agent_tool_loop
from agents.common.skill_loader import format_skills_prompt_section, load_skills_for_agent
from agents.common.traceability import AgentTracer
from agents.evaluador.prompts import (
    EVALUADOR_AGENT_NAME,
    EVALUADOR_ALLOWED_SKILLS,
    EVALUADOR_ALLOWED_TOOLS,
    EVALUADOR_BASE_INSTRUCTIONS,
    EVALUADOR_TOOL_DECLARATIONS,
    EVALUADOR_TOOL_ORDER_PRIORITY,
    build_evaluador_user_prompt,
)
from agents.evaluador.result_builder import build_validated_evaluation_result
from agents.tools.evaluation_tools import (
    EvaluationSessionState,
    execute_tool_asignar_nivel_riesgo,
    execute_tool_calcular_puntaje,
    execute_tool_explicar_resultado,
    execute_tool_generar_pdf,
    execute_tool_recomendar_cuidados,
    execute_tool_reunir_hallazgos,
)
from agents.tools.preparation_tools import PreparationSessionContext

# Re-exportación explícita de constantes para compatibilidad con pruebas y módulos externos
__all__ = [
    "EVALUADOR_AGENT_NAME",
    "EVALUADOR_ALLOWED_SKILLS",
    "EVALUADOR_ALLOWED_TOOLS",
    "EVALUADOR_BASE_INSTRUCTIONS",
    "EVALUADOR_TOOL_DECLARATIONS",
    "EVALUADOR_TOOL_ORDER_PRIORITY",
    "EvaluadorAgent",
]


class EvaluadorAgent:
    """
    Agente Evaluador que consolida hallazgos, ejecuta el cómputo de riesgo determinístico en Python,
    genera la explicación, recomendaciones y PDF opcional utilizando sus 6 skills.
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        model_name: Optional[str] = None,
        policy_override: Optional[Dict[str, Any]] = None,
        analyzer_override: Optional[Any] = None,
    ) -> None:
        self.name = EVALUADOR_AGENT_NAME
        self.llm_client = llm_client
        self.model_name = model_name or DEFAULT_GEMINI_MODEL
        self.policy_override = policy_override
        self.analyzer_override = analyzer_override
        self.loaded_skills = load_skills_for_agent(self.name, EVALUADOR_ALLOWED_SKILLS)

    def build_system_instruction(self) -> str:
        """Construye las instrucciones de sistema combinando la base y las 6 skills cargadas."""
        skills_section = format_skills_prompt_section(self.loaded_skills)
        return f"{EVALUADOR_BASE_INSTRUCTIONS}\n\n{skills_section}"

    def run(
        self,
        session_ctx: PreparationSessionContext,
        prep_res: PreparationResult,
        msg_res: MessageAnalysisResult,
        url_res: Optional[UrlAnalysisResult],
        tracer: AgentTracer,
        generate_pdf: bool = False,
        save_pdf_to_output: bool = False,
        max_elapsed_seconds: float = 20.0,
    ) -> EvaluationResult:
        """
        Ejecuta el Agente Evaluador sobre los resultados validados de las etapas previas.
        """
        t0 = time.monotonic()
        tracer.record(
            agent=self.name,
            event_type="agent_start",
            tool="none",
            status="ok",
            detail=f"Iniciando Agente Evaluador (generate_pdf={generate_pdf}).",
        )

        for s_name, s_def in self.loaded_skills.items():
            tracer.record(
                agent=self.name,
                event_type="skill_loaded",
                tool=s_def.tool_name,
                status="ok",
                detail=f"Skill '{s_name}' cargada desde SKILL.md.",
            )

        eval_state = EvaluationSessionState(
            raw_text=getattr(session_ctx, "raw_active_text", "") or prep_res.texto_extraido_o_recibido,
            input_mode=session_ctx.input_mode,
            prep_res=prep_res,
            msg_res=msg_res,
            url_res=url_res,
            session_ctx=session_ctx,
            policy_override=self.policy_override,
            analyzer_override=self.analyzer_override,
        )

        allowed_tools_map: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            "tool_reunir_hallazgos": lambda args: execute_tool_reunir_hallazgos(
                session_ctx, eval_state, args,
                analyzer_override=self.analyzer_override,
                policy_override=self.policy_override,
            ),
            "tool_calcular_puntaje": lambda args: execute_tool_calcular_puntaje(
                eval_state, args, policy_override=self.policy_override,
            ),
            "tool_asignar_nivel_riesgo": lambda args: execute_tool_asignar_nivel_riesgo(
                eval_state, args, policy_override=self.policy_override,
            ),
            "tool_explicar_resultado": lambda args: execute_tool_explicar_resultado(
                eval_state, args,
            ),
            "tool_recomendar_cuidados": lambda args: execute_tool_recomendar_cuidados(
                eval_state, args,
            ),
            "tool_generar_pdf": lambda args: execute_tool_generar_pdf(
                eval_state, args,
            ),
        }

        user_prompt = build_evaluador_user_prompt(
            input_mode=session_ctx.input_mode,
            prep_res=prep_res,
            msg_res=msg_res,
            url_res=url_res,
            generate_pdf=generate_pdf,
            save_pdf_to_output=save_pdf_to_output,
        )

        run_agent_tool_loop(
            agent_name=self.name,
            system_instruction=self.build_system_instruction(),
            user_prompt=user_prompt,
            allowed_tools=allowed_tools_map,
            tool_declarations=EVALUADOR_TOOL_DECLARATIONS,
            tracer=tracer,
            llm_client=self.llm_client,
            model_name=self.model_name,
            max_tool_calls=8,
            max_elapsed_seconds=max_elapsed_seconds,
            tool_order_priority=EVALUADOR_TOOL_ORDER_PRIORITY,
        )

        result = self._build_validated_result(eval_state, prep_res, msg_res, url_res)
        elapsed_ms = (time.monotonic() - t0) * 1000
        tracer.record(
            agent=self.name,
            event_type="agent_finish",
            tool="none",
            status="ok" if result.estado == "correcto" else "incomplete",
            detail=(
                f"Evaluación finalizada: estado='{result.estado}', nivel='{result.nivel_riesgo}', "
                f"puntaje={result.puntaje}/100, reglas_activadas={len(result.reglas_activadas)}."
            ),
            duration_ms=elapsed_ms,
        )
        return result

    def _build_validated_result(
        self,
        state: EvaluationSessionState,
        prep_res: PreparationResult,
        msg_res: MessageAnalysisResult,
        url_res: Optional[UrlAnalysisResult],
    ) -> EvaluationResult:
        """Delega la construcción y validación del contrato en `result_builder.py`."""
        return build_validated_evaluation_result(
            state=state,
            prep_res=prep_res,
            msg_res=msg_res,
            url_res=url_res,
            loaded_skills=list(self.loaded_skills.keys()),
        )
