"""
Pruebas Unitarias de Métricas de Consumo de Tokens (Sin Red).

Verifica exhaustivamente el tratamiento riguroso de tokens en AgentTracer y llm_client:
- Metadatos completos.
- Metadatos ausentes (None).
- Campos None distinguidos de ceros (0) informados.
- Ceros explícitos certificados.
- Solo total disponible (caso histórico: total=3022, componentes ausentes).
- Cobertura mixta a través de múltiples llamadas.
- Agregación por agente y total global sin doble conteo.
- Llamadas fallidas sin datos de consumo (no deben registrar consumo cero confirmado).
- Separación de llamadas lógicas y reintentos.
- Registro diferenciado de tokens de caché y razonamiento (thoughts).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import pytest

from agents.common.traceability import AgentTracer, LLMCallRecord
from agents.common.llm_client import run_agent_tool_loop


class DummyUsageMetadata:
    """Simula GenerateContentResponseUsageMetadata de google-genai."""
    def __init__(
        self,
        prompt_token_count: Optional[int] = None,
        candidates_token_count: Optional[int] = None,
        total_token_count: Optional[int] = None,
        cached_content_token_count: Optional[int] = None,
        thoughts_token_count: Optional[int] = None,
        tool_use_prompt_token_count: Optional[int] = None,
    ) -> None:
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count
        self.total_token_count = total_token_count
        self.cached_content_token_count = cached_content_token_count
        self.thoughts_token_count = thoughts_token_count
        self.tool_use_prompt_token_count = tool_use_prompt_token_count


class DummyGenerateContentResponse:
    """Respuesta simulada compatible con generate_content."""
    def __init__(
        self,
        text: str = "Respuesta final simulada",
        usage_metadata: Optional[DummyUsageMetadata] = None,
        function_calls: Optional[List[Any]] = None,
    ) -> None:
        self.text = text
        self.usage_metadata = usage_metadata
        self.function_calls = function_calls or []
        self.candidates = []


class DummyModelsClient:
    """Cliente simulado de modelos para run_agent_tool_loop."""
    def __init__(self, responses: List[DummyGenerateContentResponse]) -> None:
        self._responses = list(responses)
        self.calls_history: List[Dict[str, Any]] = []

    def generate_content(self, model: str, contents: Any, config: Any) -> DummyGenerateContentResponse:
        self.calls_history.append({"model": model, "contents": contents, "config": config})
        if not self._responses:
            raise RuntimeError("No hay más respuestas simuladas configuradas")
        return self._responses.pop(0)


class DummyMockLLMClient:
    """Envoltura de cliente simulado."""
    def __init__(self, responses: List[DummyGenerateContentResponse]) -> None:
        self.is_mock_client = True
        self.models = DummyModelsClient(responses)


# =============================================================================
# 1. Pruebas Directas sobre AgentTracer
# =============================================================================

def test_tracer_complete_usage_metadata():
    """Verifica el registro cuando todos los metadatos de tokens están disponibles."""
    tracer = AgentTracer()
    tracer.record_llm_usage(
        agent="preparador",
        prompt_tokens=120,
        output_tokens=45,
        total_tokens=165,
        cached_tokens=10,
        thoughts_tokens=20,
        tool_use_prompt_tokens=15,
        is_retry=False,
        success=True,
        model="gemini-3.5-flash-lite",
    )

    summary = tracer.get_usage_summary()
    assert summary["llm_calls_total"] == 1
    assert summary["llm_retries_total"] == 0
    assert summary["prompt_tokens_total"] == 120
    assert summary["output_tokens_total"] == 45
    assert summary["total_tokens"] == 165
    assert summary["cached_tokens_total"] == 10
    assert summary["thoughts_tokens_total"] == 20
    assert summary["tool_use_prompt_tokens_total"] == 15
    assert summary["coverage"]["status"] == "complete"
    assert summary["coverage"]["calls_with_complete_usage"] == 1
    assert summary["display"]["total_tokens"] == "165"
    assert summary["display"]["prompt_tokens"] == "120"
    assert summary["display"]["output_tokens"] == "45"

    by_ag = summary["by_agent"]["preparador"]
    assert by_ag["llm_calls"] == 1
    assert by_ag["prompt_tokens"] == 120
    assert by_ag["total_tokens"] == 165
    assert by_ag["coverage"] == "complete"


def test_tracer_missing_usage_metadata():
    """Verifica que llamadas sin metadatos de uso se registren como 'unavailable' y None."""
    tracer = AgentTracer()
    tracer.record_llm_usage(
        agent="analizador_mensajes",
        prompt_tokens=None,
        output_tokens=None,
        total_tokens=None,
        model="gemini-3.5-flash-lite",
    )

    summary = tracer.get_usage_summary()
    assert summary["llm_calls_total"] == 1
    assert summary["prompt_tokens_total"] is None
    assert summary["output_tokens_total"] is None
    assert summary["total_tokens"] is None
    assert summary["coverage"]["status"] == "unavailable"
    assert summary["coverage"]["calls_without_usage"] == 1
    assert summary["display"]["total_tokens"] == "no disponible"
    assert summary["display"]["prompt_tokens"] == "no disponible"


def test_tracer_distinguishes_none_from_explicit_zero():
    """
    Verifica que un valor None (no informado) NO se convierta en cero,
    y que un cero explícito (0 informado) se certifique como consumo confirmado.
    """
    tracer = AgentTracer()

    # Caso A: Ceros explícitos (ej. endpoint certifica 0 tokens consumidos)
    tracer.record_llm_usage(
        agent="agente_cero",
        prompt_tokens=0,
        output_tokens=0,
        total_tokens=0,
        model="modelo_test",
    )
    summary_cero = tracer.get_usage_summary()["by_agent"]["agente_cero"]
    assert summary_cero["prompt_tokens"] == 0
    assert summary_cero["output_tokens"] == 0
    assert summary_cero["total_tokens"] == 0
    assert summary_cero["coverage"] == "complete"
    assert summary_cero["prompt_tokens"] is not None

    # Caso B: Campos ausentes / None (ej. endpoint no desglosa componentes)
    tracer_none = AgentTracer()
    tracer_none.record_llm_usage(
        agent="agente_none",
        prompt_tokens=None,
        output_tokens=None,
        total_tokens=300,
        model="modelo_test",
    )
    summary_none = tracer_none.get_usage_summary()["by_agent"]["agente_none"]
    assert summary_none["prompt_tokens"] is None
    assert summary_none["output_tokens"] is None
    assert summary_none["total_tokens"] == 300
    assert summary_none["coverage"] == "partial"


def test_tracer_only_total_available_historical_case():
    """
    Reproduce exactamente el caso histórico (prompt=None, output=None, total=3022):
    - Conserva el total reportado por el proveedor (3022).
    - No inventa componentes (prompt y output quedan en None, no en 0).
    - Informa que la cobertura es parcial y muestra display adecuado.
    """
    tracer = AgentTracer()
    tracer.record_llm_usage(
        agent="analizador_enlaces",
        prompt_tokens=None,
        output_tokens=None,
        total_tokens=3022,
        model="gemini-3.5-flash-lite",
    )

    summary = tracer.get_usage_summary()
    assert summary["total_tokens"] == 3022
    assert summary["prompt_tokens_total"] is None
    assert summary["output_tokens_total"] is None
    assert summary["coverage"]["status"] == "partial"
    assert summary["coverage"]["calls_with_partial_usage"] == 1
    assert summary["prompt_tokens_coverage"] == "unavailable"
    assert summary["total_tokens_coverage"] == "complete"
    assert summary["display"]["total_tokens"] == "3022"
    assert summary["display"]["prompt_tokens"] == "no disponible"


def test_tracer_mixed_coverage_across_multiple_calls():
    """Verifica la agregación cuando varias llamadas presentan coberturas heterogéneas."""
    tracer = AgentTracer()

    # Llamada 1: Completa
    tracer.record_llm_usage("orquestador", prompt_tokens=100, output_tokens=30, total_tokens=130)
    # Llamada 2: Solo total disponible
    tracer.record_llm_usage("orquestador", prompt_tokens=None, output_tokens=None, total_tokens=250)
    # Llamada 3: Sin datos de uso
    tracer.record_llm_usage("orquestador", prompt_tokens=None, output_tokens=None, total_tokens=None)

    summary = tracer.get_usage_summary()
    assert summary["llm_calls_total"] == 3
    # Prompt: 100 de la única llamada que lo informó
    assert summary["prompt_tokens_total"] == 100
    assert summary["prompt_tokens_coverage"] == "partial"
    # Output: 30 de la única llamada que lo informó
    assert summary["output_tokens_total"] == 30
    assert summary["output_tokens_coverage"] == "partial"
    # Total: 130 + 250 = 380 de las dos llamadas que lo informaron
    assert summary["total_tokens"] == 380
    assert summary["total_tokens_coverage"] == "partial"
    assert summary["coverage"]["status"] == "partial"
    assert summary["coverage"]["calls_with_complete_usage"] == 1
    assert summary["coverage"]["calls_with_partial_usage"] == 1
    assert summary["coverage"]["calls_without_usage"] == 1
    assert "380 (parcial: 2/3 llamadas)" == summary["display"]["total_tokens"]
    assert "100 (parcial: 1/3 llamadas)" == summary["display"]["prompt_tokens"]


def test_tracer_aggregation_by_agent_no_double_counting():
    """
    Verifica que la agregación global sume estrictamente las llamadas
    de cada agente sin solapamiento ni doble conteo entre orquestador y especialistas.
    """
    tracer = AgentTracer()

    tracer.record_llm_usage("orquestador", prompt_tokens=150, output_tokens=40, total_tokens=190)
    tracer.record_llm_usage("preparador", prompt_tokens=200, output_tokens=50, total_tokens=250)
    tracer.record_llm_usage("analizador_mensajes", prompt_tokens=300, output_tokens=70, total_tokens=370)
    tracer.record_llm_usage("evaluador", prompt_tokens=250, output_tokens=60, total_tokens=310)

    summary = tracer.get_usage_summary()
    assert summary["llm_calls_total"] == 4
    assert summary["total_tokens"] == 190 + 250 + 370 + 310  # 1120
    assert summary["prompt_tokens_total"] == 150 + 200 + 300 + 250  # 900
    assert summary["output_tokens_total"] == 40 + 50 + 70 + 60  # 220

    by_ag = summary["by_agent"]
    assert len(by_ag) == 4
    # La suma de cada agente debe ser exactamente igual al total global
    sum_by_agents = sum(ag["total_tokens"] for ag in by_ag.values())
    assert sum_by_agents == summary["total_tokens"]
    assert by_ag["orquestador"]["total_tokens"] == 190
    assert by_ag["preparador"]["total_tokens"] == 250
    assert by_ag["analizador_mensajes"]["total_tokens"] == 370
    assert by_ag["evaluador"]["total_tokens"] == 310


def test_tracer_failed_call_does_not_impute_zero():
    """
    Verifica que una llamada fallida antes de recibir respuesta:
    - NO se compute como 0 tokens confirmados.
    - Se marque como error en el registro y no altere los consumos válidos.
    """
    tracer = AgentTracer()

    # Llamada 1 exitosa
    tracer.record_llm_usage("orquestador", prompt_tokens=100, output_tokens=20, total_tokens=120)
    # Llamada 2 fallida (timeout / error de red)
    tracer.record_llm_call_failure(
        agent="orquestador",
        model="gemini-3.5-flash-lite",
        error_type="TimeoutError",
        is_retry=False,
    )

    summary = tracer.get_usage_summary()
    assert summary["llm_calls_total"] == 2
    # El total de tokens sigue siendo 120 (de la llamada que tuvo datos), no se imputó 0
    assert summary["total_tokens"] == 120
    assert summary["coverage"]["status"] == "partial"
    assert summary["coverage"]["calls_without_usage"] == 1

    calls = tracer.get_llm_calls()
    assert len(calls) == 2
    assert calls[1]["success"] is False
    assert calls[1]["error_type"] == "TimeoutError"
    assert calls[1]["total_tokens"] is None


def test_tracer_separates_logical_calls_and_retries():
    """Verifica que las llamadas lógicas se distingan de los reintentos del cliente."""
    tracer = AgentTracer()

    # Intento 1 (falló con 429 temporal)
    tracer.record_llm_call_failure("analizador_enlaces", error_type="RateLimit429", is_retry=False)
    # Intento 2 (reintento exitoso con tokens)
    tracer.record_llm_usage("analizador_enlaces", prompt_tokens=200, output_tokens=50, total_tokens=250, is_retry=True)

    summary = tracer.get_usage_summary()
    assert summary["llm_calls_total"] == 1  # 1 llamada lógica
    assert summary["llm_retries_total"] == 1  # 1 reintento
    assert summary["llm_total_attempts"] == 2  # 2 intentos en total
    assert summary["total_tokens"] == 250


def test_tracer_distinct_cached_and_thoughts_tokens():
    """Verifica que los tokens de caché y razonamiento se registren por separado sin sumarse."""
    tracer = AgentTracer()
    tracer.record_llm_usage(
        agent="evaluador",
        prompt_tokens=500,
        output_tokens=100,
        total_tokens=650,
        cached_tokens=200,
        thoughts_tokens=80,
    )

    summary = tracer.get_usage_summary()
    assert summary["cached_tokens_total"] == 200
    assert summary["thoughts_tokens_total"] == 80
    assert summary["cached_tokens_coverage"] == "complete"
    assert summary["thoughts_tokens_coverage"] == "complete"
    # No se fuerza ninguna relación aditiva arbitraria entre caché/thoughts y total
    assert summary["total_tokens"] == 650


# =============================================================================
# 2. Pruebas de Integración con run_agent_tool_loop (Simulado)
# =============================================================================

def test_run_agent_tool_loop_extracts_usage_correctly_with_mock():
    """
    Verifica que run_agent_tool_loop extraiga de forma fiel los metadatos
    de respuesta simulada y los registre en AgentTracer.
    """
    tracer = AgentTracer()
    usage = DummyUsageMetadata(
        prompt_token_count=180,
        candidates_token_count=45,
        total_token_count=225,
        cached_content_token_count=30,
        thoughts_token_count=None,
    )
    mock_resp = DummyGenerateContentResponse(
        text="Resultado evaluado",
        usage_metadata=usage,
    )
    mock_client = DummyMockLLMClient([mock_resp])

    result = run_agent_tool_loop(
        agent_name="test_agent",
        system_instruction="Instrucción de prueba",
        user_prompt="Mensaje a analizar",
        allowed_tools={},
        tool_declarations=[],
        tracer=tracer,
        llm_client=mock_client,
    )

    assert result["final_text"] == "Resultado evaluado"
    assert result["prompt_tokens"] == 180
    assert result["output_tokens"] == 45
    assert result["total_tokens"] == 225

    summary = tracer.get_usage_summary()
    assert summary["llm_calls_total"] == 1
    assert summary["total_tokens"] == 225
    assert summary["cached_tokens_total"] == 30
    assert summary["thoughts_tokens_total"] is None  # no informado


def test_run_agent_tool_loop_handles_missing_usage_metadata():
    """
    Verifica que cuando un cliente simulado omite usage_metadata (usage is None),
    run_agent_tool_loop no registre ceros falsos sino valores None.
    """
    tracer = AgentTracer()
    mock_resp = DummyGenerateContentResponse(
        text="Respuesta sin metadatos",
        usage_metadata=None,
    )
    mock_client = DummyMockLLMClient([mock_resp])

    result = run_agent_tool_loop(
        agent_name="test_agent_no_usage",
        system_instruction="Instrucción",
        user_prompt="Prompt",
        allowed_tools={},
        tool_declarations=[],
        tracer=tracer,
        llm_client=mock_client,
    )

    assert result["prompt_tokens"] is None
    assert result["output_tokens"] is None
    assert result["total_tokens"] is None

    summary = tracer.get_usage_summary()
    assert summary["coverage"]["status"] == "unavailable"
    assert summary["display"]["total_tokens"] == "no disponible"
