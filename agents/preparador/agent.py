"""
Agente Preparador Real (`agents/preparador/agent.py`).

Responsabilidad delimitada (Coordinador):
- Carga dinámicamente sus 3 skills autorizadas desde `.agents/skills/`:
  1. `validar-entrada` -> `tool_validar_entrada`
  2. `extraer-texto-captura` -> `tool_extraer_texto_captura`
  3. `extraer-enlaces` -> `tool_extraer_enlaces`
- Ensambla las instrucciones de sistema combinando la base y las skills cargadas.
- Ejecuta el bucle real de herramientas con el modelo de IA (`run_agent_tool_loop`).
- Registra eventos de trazabilidad en `AgentTracer`.
- Delega la construcción y validación estricta de `PreparationResult` en `result_builder.py`.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from agents.common.contracts import PreparationResult
from agents.common.llm_client import run_agent_tool_loop
from agents.common.skill_loader import format_skills_prompt_section, load_skills_for_agent
from agents.common.traceability import AgentTracer
from agents.preparador.prompts import (
    PREPARADOR_AGENT_NAME,
    PREPARADOR_ALLOWED_SKILLS,
    PREPARADOR_ALLOWED_TOOLS,
    PREPARADOR_BASE_INSTRUCTIONS,
    PREPARADOR_TOOL_DECLARATIONS,
    PREPARADOR_TOOL_ORDER_PRIORITY,
    build_preparador_user_prompt,
)
from agents.preparador.result_builder import build_validated_preparation_result
from agents.tools.preparation_tools import (
    PreparationSessionContext,
    execute_tool_extraer_enlaces,
    execute_tool_extraer_texto_captura,
    execute_tool_validar_entrada,
)

# Re-exportación explícita de constantes para compatibilidad con pruebas y módulos externos
__all__ = [
    "PREPARADOR_AGENT_NAME",
    "PREPARADOR_ALLOWED_SKILLS",
    "PREPARADOR_ALLOWED_TOOLS",
    "PREPARADOR_BASE_INSTRUCTIONS",
    "PREPARADOR_TOOL_DECLARATIONS",
    "PREPARADOR_TOOL_ORDER_PRIORITY",
    "PreparadorAgent",
]


class PreparadorAgent:
    """
    Agente Preparador de Entrada y Sanitización.
    Carga dinámicamente sus 3 skills autorizadas y ejecuta el ciclo de herramientas Python.
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        model_name: Optional[str] = None,
    ) -> None:
        self.name = PREPARADOR_AGENT_NAME
        self.llm_client = llm_client
        self.model_name = model_name
        self.loaded_skills = load_skills_for_agent(self.name, PREPARADOR_ALLOWED_SKILLS)

    def build_system_instruction(self) -> str:
        """
        Construye la instrucción del sistema agregando el contenido formateado
        de cada SKILL.md autorizado para el Agente Preparador.
        """
        skills_section = format_skills_prompt_section(self.loaded_skills)
        return f"{PREPARADOR_BASE_INSTRUCTIONS}\n\n{skills_section}"

    def run(
        self,
        session_ctx: PreparationSessionContext,
        tracer: AgentTracer,
        max_elapsed_seconds: float = 20.0,
    ) -> PreparationResult:
        """
        Ejecuta el Agente Preparador real en el contexto de la sesión actual.
        """
        t0 = time.monotonic()
        tracer.record(
            agent=self.name,
            event_type="agent_start",
            tool="none",
            status="ok",
            detail=f"Iniciando Agente Preparador para entrada en modo '{session_ctx.input_mode}'.",
        )

        for s_name, s_def in self.loaded_skills.items():
            tracer.record(
                agent=self.name,
                event_type="skill_loaded",
                tool=s_def.tool_name,
                status="ok",
                detail=f"Skill '{s_name}' cargada desde SKILL.md.",
            )

        allowed_tools_map: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            "tool_validar_entrada": lambda args: execute_tool_validar_entrada(session_ctx, args),
            "tool_extraer_texto_captura": lambda args: execute_tool_extraer_texto_captura(session_ctx, args),
            "tool_extraer_enlaces": lambda args: execute_tool_extraer_enlaces(session_ctx, args),
        }

        user_prompt = build_preparador_user_prompt(session_ctx.input_mode)

        run_agent_tool_loop(
            agent_name=self.name,
            system_instruction=self.build_system_instruction(),
            user_prompt=user_prompt,
            allowed_tools=allowed_tools_map,
            tool_declarations=PREPARADOR_TOOL_DECLARATIONS,
            tracer=tracer,
            llm_client=self.llm_client,
            model_name=self.model_name,
            max_tool_calls=5,
            max_elapsed_seconds=max_elapsed_seconds,
            tool_order_priority=PREPARADOR_TOOL_ORDER_PRIORITY,
        )

        result = self._build_validated_result(session_ctx)
        elapsed_ms = (time.monotonic() - t0) * 1000
        tracer.record(
            agent=self.name,
            event_type="agent_finish",
            tool="none",
            status="ok" if result.estado == "correcto" else ("incomplete" if result.estado == "incompleto" else "error"),
            detail=f"Preparación finalizada: estado='{result.estado}', detalle='{result.detalle_estado}', enlaces={len(result.enlaces_encontrados)}.",
            duration_ms=elapsed_ms,
        )
        return result

    def _build_validated_result(self, ctx: PreparationSessionContext) -> PreparationResult:
        """Delega la construcción y validación del contrato en `result_builder.py`."""
        return build_validated_preparation_result(ctx, list(self.loaded_skills.keys()))
