"""
Módulo de Medición del Contexto Efectivamente Enviado al Modelo de IA.

Proporciona utilidades para:
- Capturar copias independientes de cada solicitud cursada al LLM.
- Medir de forma determinística y canónica el tamaño de:
  * Instrucción de sistema (system_instruction).
  * Declaraciones de herramientas (tool_declarations).
  * Contenido e historial enviados (contents).
  * Respuestas de herramientas incluidas en ese historial (tool_responses_breakdown).
- Informar caracteres (`len(str)`) y bytes UTF-8 (`len(str.encode('utf-8'))`).
- Mantener la respuesta de herramientas como desglose explicativo sin duplicarla en el total.

Aclaración de Arquitectura:
Las cifras reportadas representan caracteres de texto y bytes UTF-8 de las estructuras
serializadas; NO deben denominarse tokens de IA ni bytes exactos de tráfico de red HTTP.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any, Dict, List, Optional


def _to_canonical_serializable(obj: Any) -> Any:
    """Convierte objetos de google-genai o tipos arbitrarios a estructuras estándar serializables."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _to_canonical_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_canonical_serializable(x) for x in obj]
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return _to_canonical_serializable(obj.to_dict())
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        return _to_canonical_serializable(obj.model_dump())
    if hasattr(obj, "__dict__"):
        return {k: _to_canonical_serializable(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)


def canonical_json_serialize(obj: Any) -> str:
    """Serializa determinísticamente a JSON con claves ordenadas y formato compacto."""
    canonical = _to_canonical_serializable(obj)
    return json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def measure_text_size(text: str) -> Dict[str, int]:
    """Calcula caracteres y bytes UTF-8 exactos de una cadena."""
    encoded = text.encode("utf-8")
    return {
        "chars": len(text),
        "bytes_utf8": len(encoded),
    }


def extract_system_instruction_text(config: Any) -> str:
    """Extrae el texto de la instrucción de sistema desde config (objeto o dict)."""
    if config is None:
        return ""
    sys_inst = None
    if isinstance(config, dict):
        sys_inst = config.get("system_instruction")
    else:
        sys_inst = getattr(config, "system_instruction", None)

    if sys_inst is None:
        return ""
    if isinstance(sys_inst, str):
        return sys_inst
    if isinstance(sys_inst, dict):
        parts = sys_inst.get("parts", [])
        return "\n".join(p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p)
    # google-genai Content
    if hasattr(sys_inst, "parts"):
        parts_texts = []
        for p in sys_inst.parts:
            if hasattr(p, "text") and p.text:
                parts_texts.append(p.text)
        return "\n".join(parts_texts)
    return str(sys_inst)


def extract_tool_declarations_canonical(config: Any) -> List[Dict[str, Any]]:
    """Extrae las declaraciones de herramientas desde config en estructura canónica."""
    if config is None:
        return []
    tools = []
    if isinstance(config, dict):
        tools = config.get("tools") or []
    else:
        tools = getattr(config, "tools", None) or []

    decls: List[Dict[str, Any]] = []
    for t in tools:
        if isinstance(t, dict):
            if "name" in t and "description" in t:
                decls.append({
                    "name": t.get("name"),
                    "description": t.get("description"),
                    "parameters": _to_canonical_serializable(t.get("parameters")),
                })
            elif "function_declarations" in t:
                for fd in t["function_declarations"]:
                    decls.append({
                        "name": fd.get("name"),
                        "description": fd.get("description"),
                        "parameters": _to_canonical_serializable(fd.get("parameters")),
                    })
        elif hasattr(t, "function_declarations") and t.function_declarations:
            for fd in t.function_declarations:
                decls.append({
                    "name": getattr(fd, "name", ""),
                    "description": getattr(fd, "description", ""),
                    "parameters": _to_canonical_serializable(getattr(fd, "parameters", None)),
                })
    return decls


def extract_contents_canonical(contents: Any) -> List[Dict[str, Any]]:
    """Normaliza la lista de turnos e historial a una lista de diccionarios canónicos."""
    if not contents:
        return []
    if isinstance(contents, str):
        return [{"role": "user", "parts": [{"text": contents}]}]
    if isinstance(contents, dict):
        contents = [contents]

    normalized: List[Dict[str, Any]] = []
    for item in contents:
        if isinstance(item, dict):
            normalized.append(_to_canonical_serializable(item))
        elif hasattr(item, "role") and hasattr(item, "parts"):
            parts_norm: List[Dict[str, Any]] = []
            for p in item.parts:
                part_dict: Dict[str, Any] = {}
                if hasattr(p, "text") and p.text is not None:
                    part_dict["text"] = p.text
                if hasattr(p, "function_call") and p.function_call is not None:
                    fc = p.function_call
                    part_dict["function_call"] = {
                        "name": getattr(fc, "name", ""),
                        "args": _to_canonical_serializable(getattr(fc, "args", {})),
                    }
                if hasattr(p, "function_response") and p.function_response is not None:
                    fr = p.function_response
                    part_dict["function_response"] = {
                        "name": getattr(fr, "name", ""),
                        "response": _to_canonical_serializable(getattr(fr, "response", {})),
                    }
                parts_norm.append(part_dict)
            normalized.append({"role": item.role, "parts": parts_norm})
        else:
            normalized.append({"raw": str(item)})
    return normalized


def extract_tool_responses_breakdown(canonical_contents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extrae únicamente las partes de tipo function_response presentes en el historial.
    Se utiliza como desglose informativo, sin duplicarse en el total de la solicitud.
    """
    responses: List[Dict[str, Any]] = []
    for msg in canonical_contents:
        parts = msg.get("parts") or []
        for p in parts:
            if isinstance(p, dict) and "function_response" in p:
                responses.append(p["function_response"])
    return responses


@dataclass
class TurnContextSnapshot:
    """Instantánea de medición del contexto enviado en un turno individual hacia el LLM."""
    agent: str
    turn_index: int
    model: str
    system_instruction: Dict[str, int]
    tool_declarations: Dict[str, int]
    contents: Dict[str, int]
    tool_responses_breakdown: Dict[str, int]
    total_request: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ContextRecordingCollector:
    """Colector en memoria de instantáneas de contexto por llamada."""

    def __init__(self) -> None:
        self.snapshots: List[TurnContextSnapshot] = []

    def record_turn(
        self,
        agent: str,
        model: str,
        system_instruction_raw: Any,
        config: Any,
        contents_raw: Any,
    ) -> TurnContextSnapshot:
        turn_idx = len(self.snapshots) + 1

        # 1. Instrucción de sistema
        sys_text = extract_system_instruction_text(config)
        if not sys_text and isinstance(system_instruction_raw, str):
            sys_text = system_instruction_raw
        sys_metric = measure_text_size(sys_text)

        # 2. Declaraciones de herramientas
        tools_canonical = extract_tool_declarations_canonical(config)
        tools_str = canonical_json_serialize(tools_canonical) if tools_canonical else ""
        tools_metric = measure_text_size(tools_str)

        # 3. Contenidos e historial completo
        contents_canonical = extract_contents_canonical(contents_raw)
        contents_str = canonical_json_serialize(contents_canonical) if contents_canonical else ""
        contents_metric = measure_text_size(contents_str)

        # 4. Desglose de respuestas de herramientas (dentro de contents)
        tool_responses = extract_tool_responses_breakdown(contents_canonical)
        tool_resp_str = canonical_json_serialize(tool_responses) if tool_responses else ""
        tool_resp_metric = measure_text_size(tool_resp_str)

        # 5. Total de la solicitud: system_instruction + tool_declarations + contents
        # (tool_responses NO se vuelve a sumar porque ya está dentro de contents)
        tot_chars = sys_metric["chars"] + tools_metric["chars"] + contents_metric["chars"]
        tot_bytes = sys_metric["bytes_utf8"] + tools_metric["bytes_utf8"] + contents_metric["bytes_utf8"]

        snap = TurnContextSnapshot(
            agent=agent,
            turn_index=turn_idx,
            model=model,
            system_instruction=sys_metric,
            tool_declarations=tools_metric,
            contents=contents_metric,
            tool_responses_breakdown=tool_resp_metric,
            total_request={"chars": tot_chars, "bytes_utf8": tot_bytes},
        )
        self.snapshots.append(snap)
        return snap

    def get_summary(self) -> Dict[str, Any]:
        """Calcula el total acumulado y desglose por agente."""
        by_agent: Dict[str, List[TurnContextSnapshot]] = {}
        for s in self.snapshots:
            by_agent.setdefault(s.agent, []).append(s)

        accum_chars = sum(s.total_request["chars"] for s in self.snapshots)
        accum_bytes = sum(s.total_request["bytes_utf8"] for s in self.snapshots)

        agent_summaries: Dict[str, Any] = {}
        for ag, snaps in by_agent.items():
            ag_chars = sum(s.total_request["chars"] for s in snaps)
            ag_bytes = sum(s.total_request["bytes_utf8"] for s in snaps)
            agent_summaries[ag] = {
                "turns_count": len(snaps),
                "total_chars": ag_chars,
                "total_bytes_utf8": ag_bytes,
                "turns": [s.to_dict() for s in snaps],
            }

        return {
            "total_turns": len(self.snapshots),
            "accumulated_request_chars": accum_chars,
            "accumulated_request_bytes_utf8": accum_bytes,
            "by_agent": agent_summaries,
            "snapshots": [s.to_dict() for s in self.snapshots],
        }


class ContextRecordingModelsWrapper:
    """Envoltura de cliente.models para interceptar generate_content y registrar mediciones de contexto."""

    def __init__(
        self,
        inner_models: Any,
        collector: ContextRecordingCollector,
        agent_name: str,
    ) -> None:
        self.inner_models = inner_models
        self.collector = collector
        self.agent_name = agent_name

    def generate_content(self, model: str, contents: Any, config: Any) -> Any:
        sys_inst = getattr(config, "system_instruction", None) if config else None
        self.collector.record_turn(
            agent=self.agent_name,
            model=model,
            system_instruction_raw=sys_inst,
            config=config,
            contents_raw=contents,
        )
        return self.inner_models.generate_content(model=model, contents=contents, config=config)


class ContextRecordingClientWrapper:
    """Envoltura de cliente LLM (real o simulado) que mide el contexto de cada turno sin modificar respuestas."""

    def __init__(self, inner_client: Any, collector: ContextRecordingCollector, agent_name: str) -> None:
        self.inner_client = inner_client
        self.collector = collector
        self.agent_name = agent_name
        self.is_mock_client = getattr(inner_client, "is_mock_client", False)
        self.models = ContextRecordingModelsWrapper(
            inner_models=inner_client.models,
            collector=collector,
            agent_name=agent_name,
        )
