"""
Módulo de Trazabilidad Segura de Agentes y Herramientas.

Registra eventos mínimos de auditoría para demostrar:
- Qué agente intervino (`orquestador`, `preparador`).
- Qué herramienta llamó (`delegar_preparacion`, `tool_validar_entrada`, etc.).
- Si terminó correctamente (`ok`) o falló (`error` / `rejected`).
- Duración en milisegundos.

Política de Privacidad y Seguridad en Logs:
- NUNCA registra claves de API, tokens ni variables de entorno sensibles.
- NUNCA registra mensajes completos de usuarios ni textos extraídos íntegros.
- NUNCA registra cadenas de pensamiento (chain-of-thought) internas del modelo.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal


@dataclass
class TraceEvent:
    """Evento individual de trazabilidad de la orquesta de agentes."""
    timestamp: str
    agent: str
    event_type: Literal["agent_start", "skill_loaded", "llm_call", "tool_call", "agent_finish", "agent_error"]
    tool: str
    status: Literal["ok", "incomplete", "error", "rejected"]
    detail: str
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AgentTracer:
    """Colector en memoria de eventos de trazabilidad y consumo de llamadas/tokens por ejecución."""

    def __init__(self) -> None:
        self._events: List[TraceEvent] = []
        self._llm_calls_total: int = 0
        self._tool_calls_total: int = 0
        self._prompt_tokens_total: int = 0
        self._output_tokens_total: int = 0
        self._total_tokens: int = 0
        self._usage_by_agent: Dict[str, Dict[str, int]] = {}

    def record_llm_usage(
        self,
        agent: str,
        prompt_tokens: int,
        output_tokens: int,
        total_tokens: int,
    ) -> None:
        """Acumula llamadas al modelo y tokens consumidos por agente y globales."""
        self._llm_calls_total += 1
        self._prompt_tokens_total += int(prompt_tokens)
        self._output_tokens_total += int(output_tokens)
        self._total_tokens += int(total_tokens)

        if agent not in self._usage_by_agent:
            self._usage_by_agent[agent] = {
                "llm_calls": 0,
                "prompt_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }
        self._usage_by_agent[agent]["llm_calls"] += 1
        self._usage_by_agent[agent]["prompt_tokens"] += int(prompt_tokens)
        self._usage_by_agent[agent]["output_tokens"] += int(output_tokens)
        self._usage_by_agent[agent]["total_tokens"] += int(total_tokens)

    def get_usage_summary(self) -> Dict[str, Any]:
        return {
            "llm_calls_total": self._llm_calls_total,
            "tool_calls_total": self._tool_calls_total,
            "prompt_tokens_total": self._prompt_tokens_total,
            "output_tokens_total": self._output_tokens_total,
            "total_tokens": self._total_tokens,
            "by_agent": dict(self._usage_by_agent),
        }

    def record(
        self,
        agent: str,
        event_type: Literal["agent_start", "skill_loaded", "llm_call", "tool_call", "agent_finish", "agent_error"],
        tool: str,
        status: Literal["ok", "incomplete", "error", "rejected"],
        detail: str,
        duration_ms: float = 0.0,
    ) -> None:
        if event_type == "tool_call":
            self._tool_calls_total += 1
        # Truncar detalle preventivamente y asegurar que no contenga saltos ni payloads largos
        safe_detail = str(detail).replace("\n", " ").strip()[:220]
        event = TraceEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent=agent,
            event_type=event_type,
            tool=tool,
            status=status,
            detail=safe_detail,
            duration_ms=round(float(duration_ms), 2),
        )
        self._events.append(event)

    def get_events(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._events]

