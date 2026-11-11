"""
Agente Analizador de Enlaces Real (`agents/analizador_enlaces/agent.py`).

Responsabilidad delimitada (Etapa 3 / Refactor Modular):
- Coordinador del Agente Analizador de Enlaces: carga la skill autorizada `analizar-url`.
- Ensambla las instrucciones de sistema combinando la base y el cuerpo de la skill.
- Prepara y ejecuta el bucle de herramientas con Cero Red (`run_agent_tool_loop`).
- Registra eventos de telemetría y auditoría en `AgentTracer`.
- Delega la construcción y validación exhaustiva de contratos en `result_builder.py`.
- Preserva la interfaz pública para la aplicación web y el Agente Orquestador.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from agents.analizador_enlaces.prompts import (
    ANALIZADOR_ENLACES_AGENT_NAME,
    ANALIZADOR_ENLACES_ALLOWED_SKILLS,
    ANALIZADOR_ENLACES_ALLOWED_TOOLS,
    ANALIZADOR_ENLACES_BASE_INSTRUCTIONS,
    ANALIZADOR_ENLACES_TOOL_DECLARATIONS,
    build_untrusted_urls_prompt,
)
from agents.analizador_enlaces.result_builder import build_validated_url_analysis_result
from agents.common.contracts import UrlAnalysisResult
from agents.common.llm_client import run_agent_tool_loop
from agents.common.privacy import sanitize_url_for_external_llm
from agents.common.skill_loader import format_skills_prompt_section, load_skills_for_agent
from agents.common.traceability import AgentTracer
from agents.tools.preparation_tools import PreparationSessionContext
from agents.tools.url_analysis_tools import (
    UrlAnalysisSessionState,
    execute_tool_analizar_url,
)

# Re-exportar constantes para compatibilidad hacia atrás estricta con tests existentes
__all__ = [
    "ANALIZADOR_ENLACES_AGENT_NAME",
    "ANALIZADOR_ENLACES_ALLOWED_SKILLS",
    "ANALIZADOR_ENLACES_ALLOWED_TOOLS",
    "ANALIZADOR_ENLACES_BASE_INSTRUCTIONS",
    "ANALIZADOR_ENLACES_TOOL_DECLARATIONS",
    "AnalizadorEnlacesAgent",
]


def _is_url_analysis_work_complete(
    session_ctx: PreparationSessionContext,
    url_state: UrlAnalysisSessionState,
) -> bool:
    """
    Evalúa determinísticamente si el trabajo del Agente Analizador de Enlaces ha
    concluido basándose exclusivamente en el estado local validado.

    Condiciones:
    1. La herramienta `tool_analizar_url` debió ser invocada al menos una vez.
    2. Si se produjo un error técnico irrecuperable en la herramienta (`url_state.tool_errors`),
       el trabajo concluye (no hay acciones posteriores posibles para el especialista).
    3. Si la sesión no contenía enlaces (`url_id_map` vacío), la invocación de `tool_analizar_url`
       da por concluida la tarea (devolviendo `sin_enlaces`).
    4. Todos los identificadores esperados en `session_ctx.url_id_map` deben estar
       contabilizados en `url_state.analyzed_items_by_id`.
    5. Si quedan identificadores pendientes de análisis, devuelve False para permitir
       que el ciclo continúe dentro de los límites vigentes.
    """
    if "tool_analizar_url" not in url_state.tools_called:
        return False

    if url_state.tool_errors:
        return True

    expected_ids = set(session_ctx.url_id_map.keys())
    if not expected_ids:
        return True

    analyzed_ids = set(url_state.analyzed_items_by_id.keys())
    return expected_ids.issubset(analyzed_ids)


class AnalizadorEnlacesAgent:
    """
    Agente Analizador de Enlaces ejecutado mediante el modelo de IA configurado,
    con carga explícita de su `SKILL.md` (`analizar-url`), validación de referencias
    de enlaces y lista cerrada de 1 herramienta (`tool_analizar_url`).
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        model_name: Optional[str] = None,
        url_analyzer_override: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> None:
        self.name = ANALIZADOR_ENLACES_AGENT_NAME
        self.llm_client = llm_client
        self.model_name = model_name
        self.url_analyzer_override = url_analyzer_override
        self.loaded_skills = load_skills_for_agent(self.name, ANALIZADOR_ENLACES_ALLOWED_SKILLS)

    def build_system_instruction(self) -> str:
        """Construye las instrucciones de sistema concatenando la base y las skills cargadas."""
        skills_section = format_skills_prompt_section(self.loaded_skills)
        return f"{ANALIZADOR_ENLACES_BASE_INSTRUCTIONS}\n\n{skills_section}"

    def run(
        self,
        session_ctx: PreparationSessionContext,
        tracer: AgentTracer,
        max_elapsed_seconds: float = 20.0,
    ) -> UrlAnalysisResult:
        """
        Ejecuta el Agente Analizador de Enlaces sobre las referencias de URL en `session_ctx`
        y devuelve un `UrlAnalysisResult` estructurado y validado.
        """
        t0 = time.monotonic()

        # Asegurar que url_id_map esté sincronizado con extracted_urls
        if not session_ctx.url_id_map and session_ctx.extracted_urls:
            session_ctx.url_id_map = {
                f"URL-{idx}": u for idx, u in enumerate(session_ctx.extracted_urls, start=1)
            }
            session_ctx.masked_url_id_map = {
                uid: sanitize_url_for_external_llm(u)[0]
                for uid, u in session_ctx.url_id_map.items()
            }

        tracer.record(
            agent=self.name,
            event_type="agent_start",
            tool="none",
            status="ok",
            detail=(
                f"Iniciando Agente Analizador de Enlaces sobre {len(session_ctx.url_id_map)} "
                f"enlace(s) extraído(s)."
            ),
        )

        for s_name, s_def in self.loaded_skills.items():
            tracer.record(
                agent=self.name,
                event_type="skill_loaded",
                tool=s_def.tool_name,
                status="ok",
                detail=f"Skill '{s_name}' cargada desde SKILL.md.",
            )

        url_state = UrlAnalysisSessionState()

        allowed_tools_map: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            "tool_analizar_url": lambda args: execute_tool_analizar_url(
                session_ctx,
                url_state,
                args,
                url_analyzer_override=self.url_analyzer_override,
            ),
        }

        user_prompt = build_untrusted_urls_prompt(
            session_ctx.url_id_map,
            session_ctx.masked_url_id_map,
        )

        def _should_terminate_early() -> bool:
            return _is_url_analysis_work_complete(session_ctx, url_state)

        run_agent_tool_loop(
            agent_name=self.name,
            system_instruction=self.build_system_instruction(),
            user_prompt=user_prompt,
            allowed_tools=allowed_tools_map,
            tool_declarations=ANALIZADOR_ENLACES_TOOL_DECLARATIONS,
            tracer=tracer,
            llm_client=self.llm_client,
            model_name=self.model_name,
            max_tool_calls=4,
            max_elapsed_seconds=max_elapsed_seconds,
            should_terminate_early=_should_terminate_early,
        )

        loaded_skill_names = list(self.loaded_skills.keys())
        result = build_validated_url_analysis_result(
            session_ctx,
            url_state,
            loaded_skill_names,
        )

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
                f"Análisis de enlaces finalizado: estado='{result.estado}', "
                f"detalle='{result.detalle_estado}', "
                f"procesados={result.cantidad_enlaces_procesados}/{result.cantidad_enlaces_extraidos}."
            ),
            duration_ms=elapsed_ms,
        )
        return result
