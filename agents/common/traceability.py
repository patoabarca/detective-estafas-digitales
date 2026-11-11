"""
Módulo de Trazabilidad Segura de Agentes, Herramientas y Consumo de Tokens.

Registra eventos mínimos de auditoría para demostrar:
- Qué agente intervino (`orquestador`, `preparador`, `analizador_mensajes`, `analizador_enlaces`, `evaluador`).
- Qué herramienta llamó (`delegar_preparacion`, `tool_validar_entrada`, `tool_analizar_url`, etc.).
- Si terminó correctamente (`ok`), de forma parcial (`incomplete`), con reintento (`warning`) o falló (`error` / `rejected`).
- Duración en milisegundos.
- Consumo exacto de tokens por llamada lógica y reintento, diferenciando datos ausentes (None) de ceros reales (0),
  tokens de caché y razonamiento, y reportando cobertura sin doble conteo entre orquestador y especialistas.

Política de Privacidad y Seguridad en Logs:
- NUNCA registra claves de API, tokens ni variables de entorno sensibles.
- NUNCA registra mensajes completos de usuarios ni textos extraídos íntegros.
- NUNCA registra cadenas de pensamiento (chain-of-thought) internas del modelo.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional


@dataclass
class TraceEvent:
    """Evento individual de trazabilidad de la orquesta de agentes."""
    timestamp: str
    agent: str
    event_type: Literal[
        "agent_start",
        "skill_loaded",
        "llm_call",
        "tool_call",
        "agent_finish",
        "agent_error",
        "agent_retry",
        "agent_skipped",
    ]
    tool: str
    status: Literal["ok", "incomplete", "error", "rejected", "warning"]
    detail: str
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LLMCallRecord:
    """
    Registro individual e inmutable de una llamada al modelo de IA.
    Diferencia llamadas lógicas de reintentos del cliente y distingue
    valores de tokens informados (>=0) de valores ausentes (None).
    """
    call_id: int
    agent: str
    model: str
    timestamp: str
    prompt_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cached_tokens: Optional[int] = None
    thoughts_tokens: Optional[int] = None
    tool_use_prompt_tokens: Optional[int] = None
    is_retry: bool = False
    success: bool = True
    error_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _compute_metric_coverage(
    records: List[LLMCallRecord],
    field_name: str,
) -> Dict[str, Any]:
    """
    Calcula el total y la cobertura de una métrica de tokens específica.
    Distingue:
    - complete: informada en el 100% de las llamadas.
    - partial: informada en al menos una llamada pero ausente en otras.
    - unavailable: ausente en todas las llamadas.
    """
    if not records:
        return {
            "total": None,
            "reported_calls": 0,
            "missing_calls": 0,
            "status": "unavailable",
        }

    reported_vals = [
        getattr(r, field_name)
        for r in records
        if getattr(r, field_name) is not None
    ]
    reported_count = len(reported_vals)
    missing_count = len(records) - reported_count

    if reported_count == 0:
        return {
            "total": None,
            "reported_calls": 0,
            "missing_calls": missing_count,
            "status": "unavailable",
        }

    total_val = sum(reported_vals)
    status: Literal["complete", "partial"] = (
        "complete" if reported_count == len(records) else "partial"
    )

    return {
        "total": total_val,
        "reported_calls": reported_count,
        "missing_calls": missing_count,
        "status": status,
    }


def _format_metric_display(cov_info: Dict[str, Any], total_calls: int) -> str:
    """Genera una representación textual legible de una métrica para interfaces de usuario."""
    status = cov_info["status"]
    total = cov_info["total"]
    if status == "unavailable" or total is None:
        return "no disponible"
    if status == "complete":
        return str(total)
    return f"{total} (parcial: {cov_info['reported_calls']}/{total_calls} llamadas)"


class AgentTracer:
    """
    Colector en memoria de eventos de auditoría y métricas de consumo de LLM por ejecución.
    Proporciona trazabilidad auditable sin duplicación entre orquestador y especialistas.
    """

    def __init__(self) -> None:
        self._events: List[TraceEvent] = []
        self._llm_calls: List[LLMCallRecord] = []
        self._tool_calls_total: int = 0

    def record_llm_usage(
        self,
        agent: str,
        prompt_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        cached_tokens: Optional[int] = None,
        thoughts_tokens: Optional[int] = None,
        tool_use_prompt_tokens: Optional[int] = None,
        is_retry: bool = False,
        success: bool = True,
        model: Optional[str] = None,
        error_type: Optional[str] = None,
    ) -> None:
        """
        Registra el consumo de una llamada individual al modelo de IA.
        Conserva valores `None` explícitos cuando el proveedor no reportó un componente.
        """
        call_id = len(self._llm_calls) + 1
        rec = LLMCallRecord(
            call_id=call_id,
            agent=agent,
            model=model or "unknown_model",
            timestamp=datetime.now(timezone.utc).isoformat(),
            prompt_tokens=int(prompt_tokens) if prompt_tokens is not None else None,
            output_tokens=int(output_tokens) if output_tokens is not None else None,
            total_tokens=int(total_tokens) if total_tokens is not None else None,
            cached_tokens=int(cached_tokens) if cached_tokens is not None else None,
            thoughts_tokens=int(thoughts_tokens) if thoughts_tokens is not None else None,
            tool_use_prompt_tokens=int(tool_use_prompt_tokens) if tool_use_prompt_tokens is not None else None,
            is_retry=bool(is_retry),
            success=bool(success),
            error_type=error_type,
        )
        self._llm_calls.append(rec)

    def record_llm_call_failure(
        self,
        agent: str,
        model: Optional[str] = None,
        error_type: Optional[str] = None,
        is_retry: bool = False,
    ) -> None:
        """
        Registra una llamada al modelo que falló antes de recibir respuesta.
        NO imputa consumo de 0 tokens, sino que registra ausencia de metadatos de uso.
        """
        self.record_llm_usage(
            agent=agent,
            prompt_tokens=None,
            output_tokens=None,
            total_tokens=None,
            cached_tokens=None,
            thoughts_tokens=None,
            tool_use_prompt_tokens=None,
            is_retry=is_retry,
            success=False,
            model=model,
            error_type=error_type,
        )

    def _summarize_records(
        self,
        records: List[LLMCallRecord],
        tool_calls: int,
    ) -> Dict[str, Any]:
        """Calcula el resumen de consumo y cobertura sobre una lista de llamadas."""
        logical_calls = [r for r in records if not r.is_retry]
        retries = [r for r in records if r.is_retry]
        successful_calls = [r for r in records if r.success]
        failed_attempts = [r for r in records if not r.success]
        total_calls_count = len(records)
        logical_calls_count = len(logical_calls)

        # Analizar métricas sobre todas las llamadas cursadas (lógicas y reintentos)
        p_cov = _compute_metric_coverage(records, "prompt_tokens")
        o_cov = _compute_metric_coverage(records, "output_tokens")
        t_cov = _compute_metric_coverage(records, "total_tokens")
        c_cov = _compute_metric_coverage(records, "cached_tokens")
        th_cov = _compute_metric_coverage(records, "thoughts_tokens")
        tu_cov = _compute_metric_coverage(records, "tool_use_prompt_tokens")

        # Conteo de llamadas según estado de sus metadatos
        calls_complete = sum(
            1 for r in records
            if r.prompt_tokens is not None
            and r.output_tokens is not None
            and r.total_tokens is not None
        )
        calls_without = sum(
            1 for r in records
            if r.prompt_tokens is None
            and r.output_tokens is None
            and r.total_tokens is None
            and r.cached_tokens is None
            and r.thoughts_tokens is None
        )
        calls_partial = total_calls_count - calls_complete - calls_without

        if total_calls_count == 0:
            overall_status: Literal["complete", "partial", "unavailable"] = "unavailable"
        elif calls_complete == total_calls_count:
            overall_status = "complete"
        elif calls_without == total_calls_count:
            overall_status = "unavailable"
        else:
            overall_status = "partial"

        return {
            "llm_calls_total": logical_calls_count,
            "llm_successful_calls_total": len(successful_calls),
            "llm_failed_attempts_total": len(failed_attempts),
            "llm_retries_total": len(retries),
            "llm_total_attempts": total_calls_count,
            "tool_calls_total": tool_calls,
            "coverage": {
                "status": overall_status,
                "calls_total": total_calls_count,
                "calls_with_complete_usage": calls_complete,
                "calls_with_partial_usage": calls_partial,
                "calls_without_usage": calls_without,
            },
            # Totales agregados (None si no hay datos informados)
            "prompt_tokens_total": p_cov["total"],
            "output_tokens_total": o_cov["total"],
            "total_tokens": t_cov["total"],
            "cached_tokens_total": c_cov["total"],
            "thoughts_tokens_total": th_cov["total"],
            "tool_use_prompt_tokens_total": tu_cov["total"],
            # Coberturas por componente
            "prompt_tokens_coverage": p_cov["status"],
            "output_tokens_coverage": o_cov["status"],
            "total_tokens_coverage": t_cov["status"],
            "cached_tokens_coverage": c_cov["status"],
            "thoughts_tokens_coverage": th_cov["status"],
            # Formatos para presentación en interfaz de usuario
            "display": {
                "total_tokens": _format_metric_display(t_cov, total_calls_count),
                "prompt_tokens": _format_metric_display(p_cov, total_calls_count),
                "output_tokens": _format_metric_display(o_cov, total_calls_count),
                "cached_tokens": _format_metric_display(c_cov, total_calls_count),
                "thoughts_tokens": _format_metric_display(th_cov, total_calls_count),
            },
        }

    def get_usage_summary(self) -> Dict[str, Any]:
        """
        Retorna el resumen consolidado de consumo de toda la ejecución y el desglose
        por cada agente individual, sin duplicación ni solapamiento.
        """
        global_summary = self._summarize_records(self._llm_calls, self._tool_calls_total)

        # Desglose por agente
        by_agent: Dict[str, Dict[str, Any]] = {}
        agents_seen = list(dict.fromkeys(r.agent for r in self._llm_calls))
        # También incluir agentes que realizaron tool calls si están en eventos
        for ev in self._events:
            if ev.agent not in agents_seen:
                agents_seen.append(ev.agent)

        for ag in agents_seen:
            ag_calls = [r for r in self._llm_calls if r.agent == ag]
            ag_tools = sum(1 for ev in self._events if ev.agent == ag and ev.event_type == "tool_call")
            ag_summary = self._summarize_records(ag_calls, ag_tools)
            # Para compatibilidad con interfaces que acceden directamente a keys simples por agente:
            by_agent[ag] = {
                "llm_calls": ag_summary["llm_calls_total"],
                "llm_successful_calls": ag_summary["llm_successful_calls_total"],
                "llm_failed_attempts": ag_summary["llm_failed_attempts_total"],
                "llm_retries": ag_summary["llm_retries_total"],
                "llm_total_attempts": ag_summary["llm_total_attempts"],
                "tool_calls": ag_tools,
                "prompt_tokens": ag_summary["prompt_tokens_total"],
                "output_tokens": ag_summary["output_tokens_total"],
                "total_tokens": ag_summary["total_tokens"],
                "cached_tokens": ag_summary["cached_tokens_total"],
                "thoughts_tokens": ag_summary["thoughts_tokens_total"],
                "coverage": ag_summary["coverage"]["status"],
                "display": ag_summary["display"],
            }

        global_summary["by_agent"] = by_agent
        return global_summary

    def record(
        self,
        agent: str,
        event_type: Literal[
            "agent_start",
            "skill_loaded",
            "llm_call",
            "tool_call",
            "agent_finish",
            "agent_error",
            "agent_retry",
            "agent_skipped",
        ],
        tool: str,
        status: Literal["ok", "incomplete", "error", "rejected", "warning"],
        detail: str,
        duration_ms: float = 0.0,
    ) -> None:
        """Registra un evento técnico de auditoría con tiempo de ejecución acotado."""
        if event_type == "tool_call":
            self._tool_calls_total += 1
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
        """Retorna la lista de eventos de auditoría registrados."""
        return [e.to_dict() for e in self._events]

    def get_llm_calls(self) -> List[Dict[str, Any]]:
        """Retorna la lista detallada de registros de llamadas individuales al LLM."""
        return [c.to_dict() for c in self._llm_calls]


def format_usage_metrics_lines(usage_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Formatea líneas legibles de resumen global y desglose por agente a partir de `usage_metrics`,
    diferenciando respuestas exitosas, intentos fallidos y reintentos registrados en el cliente
    (sin atribuirlos a solicitudes HTTP internas del SDK).
    """
    display_dict = usage_data.get("display") or {}
    tot_display = display_dict.get("total_tokens") or (
        str(usage_data.get("total_tokens")) if usage_data.get("total_tokens") is not None else "no disponible"
    )
    p_display = display_dict.get("prompt_tokens") or (
        str(usage_data.get("prompt_tokens_total")) if usage_data.get("prompt_tokens_total") is not None else "no disponible"
    )
    o_display = display_dict.get("output_tokens") or (
        str(usage_data.get("output_tokens_total")) if usage_data.get("output_tokens_total") is not None else "no disponible"
    )

    succ_calls = usage_data.get("llm_successful_calls_total", usage_data.get("llm_calls_total", 0))
    failed_attempts = usage_data.get("llm_failed_attempts_total", 0)
    retries_count = usage_data.get("llm_retries_total", 0)

    extra_parts: List[str] = []
    if failed_attempts:
        extra_parts.append(f"`{failed_attempts}` intento(s) fallido(s) sin consumo disponible")
    if retries_count:
        extra_parts.append(f"`{retries_count}` reintento(s) del cliente")
    extra_txt = f" ({', '.join(extra_parts)})" if extra_parts else ""

    summary_line = (
        f"- **Consumo acumulado de la solicitud (eventos del cliente):** "
        f"`{succ_calls}` respuestas exitosas{extra_txt}, "
        f"`{usage_data.get('tool_calls_total', 0)}` llamadas a herramientas, "
        f"`{tot_display}` tokens totales "
        f"(`{p_display}` entrada + `{o_display}` salida)."
    )

    by_agent_line = ""
    by_agent = usage_data.get("by_agent") or {}
    if by_agent:
        agent_parts: List[str] = []
        for ag_name, ag_m in by_agent.items():
            ag_disp = ag_m.get("display") or {}
            ag_tot = ag_disp.get("total_tokens") or (
                str(ag_m.get("total_tokens")) if ag_m.get("total_tokens") is not None else "no disponible"
            )
            ag_succ = ag_m.get("llm_successful_calls", ag_m.get("llm_calls", 0))
            ag_failed = ag_m.get("llm_failed_attempts", 0)
            ag_retries = ag_m.get("llm_retries", 0)
            ag_extra = []
            if ag_failed:
                ag_extra.append(f"{ag_failed} fallo(s)")
            if ag_retries:
                ag_extra.append(f"{ag_retries} reintento(s)")
            ag_extra_txt = f" ({', '.join(ag_extra)})" if ag_extra else ""
            agent_parts.append(
                f"`{ag_name}`: {ag_succ} resp. exitosas{ag_extra_txt} / {ag_m.get('tool_calls', 0)} tools / {ag_tot} tokens"
            )
        by_agent_line = f"- **Desglose por agente:** {' • '.join(agent_parts)}"

    return {"summary_line": summary_line, "by_agent_line": by_agent_line}
