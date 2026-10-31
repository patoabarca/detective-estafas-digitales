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
    event_type: Literal["agent_start", "skill_loaded", "tool_call", "agent_finish", "agent_error"]
    tool: str
    status: Literal["ok", "incomplete", "error", "rejected"]
    detail: str
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AgentTracer:
    """Colector en memoria de eventos de trazabilidad por ejecución."""

    def __init__(self) -> None:
        self._events: List[TraceEvent] = []

    def record(
        self,
        agent: str,
        event_type: Literal["agent_start", "skill_loaded", "tool_call", "agent_finish", "agent_error"],
        tool: str,
        status: Literal["ok", "incomplete", "error", "rejected"],
        detail: str,
        duration_ms: float = 0.0,
    ) -> None:
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

