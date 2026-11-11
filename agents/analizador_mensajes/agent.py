"""
Agente Analizador de Mensajes Real (`agents/analizador_mensajes/agent.py`).

Responsabilidad delimitada (Coordinador):
- Carga dinámicamente sus 5 skills autorizadas desde `.agents/skills/`:
  `detectar-urgencia`, `detectar-amenazas`, `detectar-premios`,
  `detectar-pedidos-datos` y `detectar-pedidos-dinero`.
- Ensambla las instrucciones del sistema y envía al modelo únicamente una vista
  sanitizada delimitada en `<untrusted_message>`.
- Ejecuta el bucle de herramientas (`run_agent_tool_loop`) habilitando invocación
  concurrente de las 5 herramientas independientes.
- Registra eventos de trazabilidad en `AgentTracer`.
- Delega la construcción y validación estricta de `MessageAnalysisResult` en `result_builder.py`.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from agents.analizador_mensajes.prompts import (
    ANALIZADOR_MENSAJES_AGENT_NAME,
    ANALIZADOR_MENSAJES_ALLOWED_SKILLS,
    ANALIZADOR_MENSAJES_ALLOWED_TOOLS,
    ANALIZADOR_MENSAJES_BASE_INSTRUCTIONS,
    ANALIZADOR_MENSAJES_TOOL_DECLARATIONS,
    build_untrusted_message_prompt,
)
from agents.analizador_mensajes.result_builder import build_validated_message_analysis_result
from agents.common.contracts import MessageAnalysisResult
from agents.common.llm_client import run_agent_tool_loop
from agents.common.skill_loader import format_skills_prompt_section, load_skills_for_agent
from agents.common.traceability import AgentTracer
from agents.tools.message_analysis_tools import (
    MessageAnalysisSessionState,
    execute_tool_detectar_amenazas,
    execute_tool_detectar_pedidos_datos,
    execute_tool_detectar_pedidos_dinero,
    execute_tool_detectar_premios,
    execute_tool_detectar_urgencia,
)
from agents.tools.preparation_tools import PreparationSessionContext

# Re-exportación explícita de constantes para compatibilidad con pruebas y módulos externos
__all__ = [
    "ANALIZADOR_MENSAJES_AGENT_NAME",
    "ANALIZADOR_MENSAJES_ALLOWED_SKILLS",
    "ANALIZADOR_MENSAJES_ALLOWED_TOOLS",
    "ANALIZADOR_MENSAJES_BASE_INSTRUCTIONS",
    "ANALIZADOR_MENSAJES_TOOL_DECLARATIONS",
    "AnalizadorMensajesAgent",
]


class AnalizadorMensajesAgent:
    """
    Agente Analizador de Mensajes ejecutado mediante el modelo de IA configurado,
    con carga explícita de sus 5 `SKILL.md`, validación de evidencia literal y
    lista cerrada de 5 herramientas.
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        model_name: Optional[str] = None,
        analyzer_override: Optional[Any] = None,
    ) -> None:
        self.name = ANALIZADOR_MENSAJES_AGENT_NAME
        self.llm_client = llm_client
        self.model_name = model_name
        self.analyzer_override = analyzer_override
        self.loaded_skills = load_skills_for_agent(self.name, ANALIZADOR_MENSAJES_ALLOWED_SKILLS)

    def build_system_instruction(self) -> str:
        """Construye las instrucciones de sistema combinando la base y las 5 skills cargadas."""
        skills_section = format_skills_prompt_section(self.loaded_skills)
        return f"{ANALIZADOR_MENSAJES_BASE_INSTRUCTIONS}\n\n{skills_section}"

    def run(
        self,
        session_ctx: PreparationSessionContext,
        tracer: AgentTracer,
        max_elapsed_seconds: float = 20.0,
    ) -> MessageAnalysisResult:
        """
        Ejecuta el Agente Analizador de Mensajes sobre el texto preparado en `session_ctx`
        y devuelve un `MessageAnalysisResult` estructurado y validado.
        """
        t0 = time.monotonic()
        tracer.record(
            agent=self.name,
            event_type="agent_start",
            tool="none",
            status="ok",
            detail="Iniciando Agente Analizador de Mensajes sobre el texto preparado.",
        )

        for s_name, s_def in self.loaded_skills.items():
            tracer.record(
                agent=self.name,
                event_type="skill_loaded",
                tool=s_def.tool_name,
                status="ok",
                detail=f"Skill '{s_name}' cargada desde SKILL.md.",
            )

        msg_state = MessageAnalysisSessionState()

        allowed_tools_map: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            "tool_detectar_urgencia": lambda args: execute_tool_detectar_urgencia(
                session_ctx, msg_state, args, analyzer_override=self.analyzer_override
            ),
            "tool_detectar_amenazas": lambda args: execute_tool_detectar_amenazas(
                session_ctx, msg_state, args, analyzer_override=self.analyzer_override
            ),
            "tool_detectar_premios": lambda args: execute_tool_detectar_premios(
                session_ctx, msg_state, args, analyzer_override=self.analyzer_override
            ),
            "tool_detectar_pedidos_datos": lambda args: execute_tool_detectar_pedidos_datos(
                session_ctx, msg_state, args, analyzer_override=self.analyzer_override
            ),
            "tool_detectar_pedidos_dinero": lambda args: execute_tool_detectar_pedidos_dinero(
                session_ctx, msg_state, args, analyzer_override=self.analyzer_override
            ),
        }

        user_prompt = build_untrusted_message_prompt(
            raw_char_count=len(session_ctx.raw_active_text),
            masked_active_text=session_ctx.masked_active_text or "",
        )

        run_agent_tool_loop(
            agent_name=self.name,
            system_instruction=self.build_system_instruction(),
            user_prompt=user_prompt,
            allowed_tools=allowed_tools_map,
            tool_declarations=ANALIZADOR_MENSAJES_TOOL_DECLARATIONS,
            tracer=tracer,
            llm_client=self.llm_client,
            model_name=self.model_name,
            max_tool_calls=8,
            max_elapsed_seconds=max_elapsed_seconds,
        )

        result = self._build_validated_result(session_ctx, msg_state)
        elapsed_ms = (time.monotonic() - t0) * 1000
        tracer.record(
            agent=self.name,
            event_type="agent_finish",
            tool="none",
            status=(
                "ok"
                if result.estado == "correcto"
                else ("incomplete" if result.estado == "incompleto" else "error")
            ),
            detail=(
                f"Análisis de mensaje finalizado: estado='{result.estado}', "
                f"revisadas={len(result.categorias_revisadas)}/5, "
                f"señales={len(result.senales_encontradas)}."
            ),
            duration_ms=elapsed_ms,
        )
        return result

    def _build_validated_result(
        self,
        prep_ctx: PreparationSessionContext,
        msg_state: MessageAnalysisSessionState,
    ) -> MessageAnalysisResult:
        """Delega la construcción y validación del contrato en `result_builder.py`."""
        return build_validated_message_analysis_result(
            prep_ctx, msg_state, list(self.loaded_skills.keys())
        )
