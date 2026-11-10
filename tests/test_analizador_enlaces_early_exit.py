"""
Pruebas Automatizadas de la Tarea 4:
Finalización Anticipada del Analizador de Enlaces y Optimización de Respuestas de Herramientas.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
import pytest

from agents.analizador_enlaces.agent import (
    AnalizadorEnlacesAgent,
    _is_url_analysis_work_complete,
)
from agents.common.contracts import (
    AgentInputRequest,
    ContractValidationError,
    UrlAnalysisResult,
)
from agents.common.llm_client import run_agent_tool_loop
from agents.common.privacy import sanitize_url_for_external_llm
from agents.common.traceability import AgentTracer
from agents.orquestador.agent import OrquestadorAgent
from agents.tools.preparation_tools import PreparationSessionContext
from agents.tools.url_analysis_tools import (
    UrlAnalysisSessionState,
    execute_tool_analizar_url,
)
from tests.test_agents_orchestration import (
    MockFunctionCall,
    MockLLMResponse,
    ScriptedMockLLMClient,
    make_standard_analizador_enlaces_mock_client,
    make_standard_analizador_mensajes_mock_client,
    make_standard_evaluador_mock_client,
    make_standard_orquestador_mock_client,
    make_standard_preparador_mock_client,
)


def _make_context(urls: List[str]) -> PreparationSessionContext:
    url_map = {f"URL-{i+1}": u for i, u in enumerate(urls)}
    masked_map = {f"URL-{i+1}": sanitize_url_for_external_llm(u)[0] for i, u in enumerate(urls)}
    return PreparationSessionContext(
        input_mode="text",
        raw_input_text=" ".join(urls) if urls else "Sin enlaces",
        validation_done=True,
        is_input_valid=True,
        links_extracted=True,
        extracted_urls=urls,
        url_id_map=url_map,
        masked_url_id_map=masked_map,
    )


def test_early_exit_single_batch_all_urls_avoid_final_summary_turn():
    """
    1. Todos los enlaces procesados en un único lote:
       Verifica que el agente finalice anticipadamente tras ejecutar la herramienta
       y que NO se realice un segundo turno al modelo para emitir un resumen descartado.
    """
    ctx = _make_context(["http://192.168.1.50/login", "https://promo-aniversario.xyz/premio"])
    call_count = 0

    def _step(contents: List[Any], config: Dict[str, Any]) -> MockLLMResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return MockLLMResponse(
                function_calls=[MockFunctionCall("tool_analizar_url", {"url_ids": ["ALL"]})]
            )
        return MockLLMResponse(text="Resumen final descartado")

    client = ScriptedMockLLMClient(_step)
    tracer = AgentTracer()
    agent = AnalizadorEnlacesAgent(llm_client=client)

    result = agent.run(ctx, tracer=tracer)

    assert result.estado == "correcto"
    assert result.cantidad_enlaces_procesados == 2
    assert len(client.models.calls_history) == 1  # Exactamente 1 llamada al LLM (sin turno de resumen)
    assert call_count == 1

    # Verificar que el evento de salida temprana fue registrado en el trazador
    early_events = [ev for ev in tracer.get_events() if ev["event_type"] == "agent_early_exit"]
    assert len(early_events) == 1
    assert "trabajo completado según estado local validado" in early_events[0]["detail"]


def test_subsets_processing_does_not_exit_early_until_all_covered():
    """
    2. Procesamiento en varios subconjuntos:
       Verifica que si el modelo procesa las URLs en dos llamadas sucesivas (lotes parciales),
       el mecanismo NO finalice anticipadamente en el turno 1, sino que permita el turno 2
       y solo finalice cuando todos los enlaces esperados hayan sido cubiertos.
    """
    ctx = _make_context(["http://192.168.1.50/login", "https://promo-aniversario.xyz/premio"])
    call_count = 0

    def _step(contents: List[Any], config: Dict[str, Any]) -> MockLLMResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Procesar solo URL-1 en el primer turno
            return MockLLMResponse(
                function_calls=[MockFunctionCall("tool_analizar_url", {"url_ids": ["URL-1"]})]
            )
        if call_count == 2:
            # Procesar URL-2 en el segundo turno
            return MockLLMResponse(
                function_calls=[MockFunctionCall("tool_analizar_url", {"url_ids": ["URL-2"]})]
            )
        return MockLLMResponse(text="Resumen final")

    client = ScriptedMockLLMClient(_step)
    tracer = AgentTracer()
    agent = AnalizadorEnlacesAgent(llm_client=client)

    result = agent.run(ctx, tracer=tracer)

    assert result.estado == "correcto"
    assert result.cantidad_enlaces_procesados == 2
    assert len(client.models.calls_history) == 2  # 2 turnos de herramientas, y el turno 3 se evita
    assert call_count == 2

    tool_events = [ev for ev in tracer.get_events() if ev["event_type"] == "tool_call"]
    assert len(tool_events) == 2


def test_repeated_and_invalid_identifiers():
    """
    3. Identificadores repetidos o inválidos:
       - Identificadores repetidos son deduplicados por la herramienta sin romper la finalización.
       - Identificadores inexistentes lanzan ContractValidationError inmediatamente.
    """
    ctx = _make_context(["http://192.168.1.50/login"])
    url_state = UrlAnalysisSessionState()

    # A. Repetidos en la misma llamada: procesa solo 1 vez
    out = execute_tool_analizar_url(ctx, url_state, {"url_ids": ["URL-1", "URL-1"]})
    assert out["status"] == "ok"
    assert out["processed_count"] == 1
    assert _is_url_analysis_work_complete(ctx, url_state) is True

    # B. Identificador inexistente
    with pytest.raises(ContractValidationError, match="Identificador de enlace inválido"):
        execute_tool_analizar_url(ctx, url_state, {"url_ids": ["URL-999"]})


def test_unparseable_url_marks_incomplete_and_exits_early():
    """
    4. URL no analizable:
       Verifica que ante una URL malformada o no parseable, el trabajo se considere
       concluido para evitar bucles, pero el contrato resultante sea 'incompleto' con
       'direccion_no_analizable', sin convertirlo jamás a 'correcto' ni 'riesgo bajo'.
    """
    ctx = _make_context(["http://dominio-invalido:999999/test"])
    mock_client = make_standard_analizador_enlaces_mock_client(["URL-1"])
    agent = AnalizadorEnlacesAgent(llm_client=mock_client)

    res = agent.run(ctx, tracer=AgentTracer())

    assert res.estado == "incompleto"
    assert res.detalle_estado == "direccion_no_analizable"
    assert res.cantidad_enlaces_procesados == 1
    assert len(mock_client.models.calls_history) == 1


def test_tool_failure_marks_error_and_exits_early():
    """
    5. Fallo de herramienta:
       Si la herramienta genera un error técnico irrecuperable (`tool_error`),
       el ciclo finaliza y el contrato resultante es 'error' con 'fallo_herramienta'.
    """
    ctx = _make_context(["http://192.168.1.50/login"])

    def failing_analyzer(url: str) -> Dict[str, Any]:
        raise RuntimeError("Fallo técnico simulado en el analizador")

    mock_client = make_standard_analizador_enlaces_mock_client(["URL-1"])
    agent = AnalizadorEnlacesAgent(
        llm_client=mock_client,
        url_analyzer_override=failing_analyzer,
    )

    res = agent.run(ctx, tracer=AgentTracer())

    assert res.estado == "error"
    assert res.detalle_estado == "fallo_herramienta"
    assert len(mock_client.models.calls_history) == 1


def test_model_terminates_without_calling_tool_marks_incomplete():
    """
    6. Modelo que termina sin llamar a la herramienta:
       Si el modelo emite texto sin llamar a la herramienta, el resultado se marca
       correctamente como 'incompleto' con 'enlaces_omitidos'.
    """
    ctx = _make_context(["http://192.168.1.50/login"])

    def _step(contents: List[Any], config: Dict[str, Any]) -> MockLLMResponse:
        return MockLLMResponse(text="Declaro que todo está en orden sin usar la herramienta.")

    mock_client = ScriptedMockLLMClient(_step)
    agent = AnalizadorEnlacesAgent(llm_client=mock_client)

    res = agent.run(ctx, tracer=AgentTracer())

    assert res.estado == "incompleto"
    assert res.detalle_estado == "enlaces_omitidos"
    assert res.cantidad_enlaces_procesados == 0
    assert len(res.enlaces_omitidos) == 1


def test_time_budget_exhaustion_in_enlaces_agent(monkeypatch):
    """
    7. Vencimiento del presupuesto de tiempo:
       Verifica que ante un presupuesto de tiempo agotado se lance AgentExecutionError.
    """
    import time
    simulated_time = [500.0]

    def fake_monotonic() -> float:
        curr = simulated_time[0]
        simulated_time[0] += 5.0
        return curr

    monkeypatch.setattr(time, "monotonic", fake_monotonic)

    ctx = _make_context(["http://192.168.1.50/login"])
    mock_client = make_standard_analizador_enlaces_mock_client(["URL-1"])
    agent = AnalizadorEnlacesAgent(llm_client=mock_client)

    with pytest.raises(Exception) as exc_info:
        agent.run(ctx, tracer=AgentTracer(), max_elapsed_seconds=0.1)

    assert "tiempo" in str(exc_info.value).lower() or "límite" in str(exc_info.value).lower()


def test_orchestrator_skips_enlaces_when_no_links():
    """
    8. Ausencia de enlaces:
       El Orquestador omite completamente al especialista Analizador de Enlaces,
       registrando 0 llamadas al modelo de enlaces.
    """
    url_mock_client = make_standard_analizador_enlaces_mock_client()
    orquestador = OrquestadorAgent(
        orquestador_llm_client=make_standard_orquestador_mock_client("text"),
        preparador_llm_client=make_standard_preparador_mock_client("text"),
        analizador_mensajes_llm_client=make_standard_analizador_mensajes_mock_client(),
        analizador_enlaces_llm_client=url_mock_client,
        evaluador_llm_client=make_standard_evaluador_mock_client(),
    )

    resp = orquestador.run(
        AgentInputRequest(
            input_mode="text",
            text_content="Mensaje urgente pero sin ningun enlace web.",
        )
    )

    assert resp.status == "success"
    assert len(url_mock_client.models.calls_history) == 0
    assert resp.url_analysis is not None
    assert resp.url_analysis.detalle_estado == "sin_enlaces"


def test_privacy_in_tool_output_and_requests_with_local_evidence_preservation():
    """
    9. Privacidad en salidas de herramientas y conservación de evidencia local:
       Comprueba que parámetros sensibles no se envíen en la respuesta al modelo,
       pero permanezcan íntegros en el estado local `url_state`.
    """
    sensitive_url = "https://banco.ejemplo.com/reset?token=XYZ987SECRET_KEY&user=victima@correo.com"
    ctx = _make_context([sensitive_url])
    url_state = UrlAnalysisSessionState()

    tool_out = execute_tool_analizar_url(ctx, url_state, {"url_ids": ["URL-1"]})
    out_json = json.dumps(tool_out, ensure_ascii=False)

    # El secreto no debe aparecer en la salida enviada al modelo
    assert "XYZ987SECRET_KEY" not in out_json
    assert "victima@correo.com" not in out_json

    # La URL original y evidencia completa deben conservarse en el estado local
    item_local = url_state.analyzed_items_by_id["URL-1"]
    assert "XYZ987SECRET_KEY" in item_local.raw_url
    assert "XYZ987SECRET_KEY" in item_local.senales_encontradas[0].evidencia


def test_functional_contract_equivalence_before_and_after():
    """
    10. Equivalencia de campos funcionales del contrato:
        Verifica que los campos funcionales del resultado sigan siendo idénticos
        a los esperados para casos sintéticos estándar.
    """
    ctx = _make_context(["http://192.168.1.50/login"])
    client = make_standard_analizador_enlaces_mock_client(["URL-1"])
    agent = AnalizadorEnlacesAgent(llm_client=client)

    res = agent.run(ctx, tracer=AgentTracer())

    assert res.estado == "correcto"
    assert res.detalle_estado == "analizados_con_senales"
    assert res.cantidad_enlaces_extraidos == 1
    assert res.cantidad_enlaces_procesados == 1
    assert len(res.enlaces_analizados) == 1
    assert res.enlaces_analizados[0].reglas_activadas == ["REGLA-URL-01"]
    assert res.herramientas_invocadas == ["tool_analizar_url"]


def test_other_agents_unaffected_early_exit_disabled_by_default():
    """
    11. Comportamiento sin cambios de los demás agentes:
        Verifica que cuando `should_terminate_early` no se provee (None),
        `run_agent_tool_loop` continúa ejecutando los turnos normales.
    """
    call_steps = 0

    class DummyClient:
        is_mock_client = True
        class DummyModels:
            def generate_content(self, model: str, contents: Any, config: Any):
                nonlocal call_steps
                call_steps += 1
                if call_steps == 1:
                    return MockLLMResponse(
                        function_calls=[MockFunctionCall("tool_test", {"param": "val"})]
                    )
                return MockLLMResponse(text="Resumen final emitido por el modelo.")
        def __init__(self):
            self.models = self.DummyModels()

    tracer = AgentTracer()
    out = run_agent_tool_loop(
        agent_name="otro_agente",
        system_instruction="instrucciones",
        user_prompt="prompt",
        allowed_tools={"tool_test": lambda args: {"status": "ok"}},
        tool_declarations=[{"name": "tool_test", "parameters": {"type": "OBJECT"}}],
        tracer=tracer,
        llm_client=DummyClient(),
        should_terminate_early=None,  # Desactivado por defecto
    )

    assert call_steps == 2  # Ambos turnos fueron ejecutados normalmente
    assert out["final_text"] == "Resumen final emitido por el modelo."
