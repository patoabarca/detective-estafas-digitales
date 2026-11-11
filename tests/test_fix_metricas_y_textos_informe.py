"""
Pruebas Específicas de Regresión para Métricas con Reintentos y Textos de Informe.

Cubre sin red ni llamadas reales a Gemini:
1. Contador de llamadas con reintento tras error transitorio en segunda llamada del agente:
   primera respuesta exitosa -> siguiente intento con error transitorio -> reintento exitoso.
2. Diferenciación explícita de respuestas exitosas, intentos fallidos y reintentos en
   AgentTracer, format_usage_metrics_lines y el resumen de consumo.
3. Explicación sin afirmaciones no sustentadas ("página falsa") cuando la URL es
   `analizado_sin_senales`, preservando puntaje y nivel en JSON, Markdown, Evaluador y PDF.
4. Distinción precisa de red/local según modo de ejecución real (local vs orquesta) y
   en limitaciones compartidas y PDF.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

import pytest

from agents.common.contracts import AgentInputRequest
from agents.common.llm_client import run_agent_tool_loop
from agents.common.traceability import AgentTracer, format_usage_metrics_lines
from agents.orquestador.agent import OrquestadorAgent
from scripts.report_generator import ReportGenerator
from scripts.worker import run_pipeline
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
from tests.test_token_metrics import DummyGenerateContentResponse, DummyUsageMetadata
from web.analysis_adapter import analyze_text
from web.pdf_exporter import generate_pdf_report


def test_call_counter_after_success_then_transient_error_then_retry_success(monkeypatch):
    """
    Reproduce exactamente:
    1. Primera respuesta exitosa (con tool call y tokens).
    2. Siguiente intento con error transitorio (429 temporal -> falla sin consumo conocido).
    3. Reintento exitoso (con respuesta final y tokens).
    Comprueba coherencia entre resumen por agente, total global, registros LLM,
    no duplicación de tokens y conservación de consumo desconocido como None/partial.
    """
    monkeypatch.setattr(time, "sleep", lambda _secs: None)

    attempt_sequence = {"count": 0}

    class RetrySecondTurnModels:
        def generate_content(self, model: str, contents: Any, config: Any):
            attempt_sequence["count"] += 1
            step = attempt_sequence["count"]
            if step == 1:
                # Primera respuesta exitosa (invoca herramienta dummy)
                return DummyGenerateContentResponse(
                    text="",
                    usage_metadata=DummyUsageMetadata(
                        prompt_token_count=1000,
                        candidates_token_count=120,
                        total_token_count=1120,
                    ),
                    function_calls=[MockFunctionCall("tool_dummy", {"ok": True})],
                )
            if step == 2:
                # Segundo turno, primer intento: error transitorio 429 recuperable
                raise RuntimeError("429 RESOURCE_EXHAUSTED: Rate limit exceeded. Please retry in 0.1s.")
            # Segundo turno, reintento exitoso
            return DummyGenerateContentResponse(
                text="Evaluación completada tras reintento.",
                usage_metadata=DummyUsageMetadata(
                    prompt_token_count=1500,
                    candidates_token_count=80,
                    total_token_count=1580,
                ),
                function_calls=[],
            )

    class RetrySecondTurnClient:
        is_mock_client = True

        def __init__(self) -> None:
            self.models = RetrySecondTurnModels()

    tracer = AgentTracer()
    loop_res = run_agent_tool_loop(
        agent_name="evaluador",
        system_instruction="Instrucciones de prueba",
        user_prompt="Prompt de prueba",
        allowed_tools={"tool_dummy": lambda args: {"status": "ok"}},
        tool_declarations=[{"name": "tool_dummy", "description": "Dummy", "parameters": {"type": "OBJECT", "properties": {}}}],
        tracer=tracer,
        llm_client=RetrySecondTurnClient(),
        max_elapsed_seconds=15.0,
    )

    assert attempt_sequence["count"] == 3
    assert loop_res["llm_calls_count"] == 2
    assert "Evaluación completada" in loop_res["final_text"]

    summary = tracer.get_usage_summary()
    ag = summary["by_agent"]["evaluador"]
    records = tracer.get_llm_calls()
    events = tracer.get_events()

    # Registros individuales: 3 intentos (1° OK, 2° fallo sin tokens, 3° reintento OK)
    assert len(records) == 3
    assert records[0]["success"] is True and records[0]["is_retry"] is False
    assert records[1]["success"] is False and records[1]["is_retry"] is False
    assert records[1]["prompt_tokens"] is None
    assert records[1]["output_tokens"] is None
    assert records[1]["total_tokens"] is None
    assert records[2]["success"] is True and records[2]["is_retry"] is True

    # Contadores agregados consistentes en total y por agente
    assert summary["llm_calls_total"] == 2
    assert summary["llm_successful_calls_total"] == 2
    assert summary["llm_failed_attempts_total"] == 1
    assert summary["llm_retries_total"] == 1
    assert summary["llm_total_attempts"] == 3

    assert ag["llm_calls"] == 2
    assert ag["llm_successful_calls"] == 2
    assert ag["llm_failed_attempts"] == 1
    assert ag["llm_retries"] == 1
    assert ag["llm_total_attempts"] == 3

    # Cobertura parcial: no imputa cero conocido al intento fallido
    assert summary["coverage"]["status"] == "partial"
    assert summary["coverage"]["calls_with_complete_usage"] == 2
    assert summary["coverage"]["calls_without_usage"] == 1

    # Suma exacta sin duplicación de tokens
    assert summary["prompt_tokens_total"] == 2500
    assert summary["output_tokens_total"] == 200
    assert summary["total_tokens"] == 2700
    assert ag["prompt_tokens"] == 2500
    assert ag["output_tokens"] == 200
    assert ag["total_tokens"] == 2700

    # Traza refleja los 2 llm_call exitosos y el agent_retry intermedio
    assert [e["event_type"] for e in events if e["event_type"] in ("llm_call", "agent_retry")] == [
        "llm_call",
        "agent_retry",
        "llm_call",
    ]

    # Presentación UI diferencia respuestas exitosas, intentos fallidos y reintentos sin atribuirlo a HTTP SDK
    formatted = format_usage_metrics_lines(summary)
    assert "`2` respuestas exitosas" in formatted["summary_line"]
    assert "`1` intento(s) fallido(s) sin consumo disponible" in formatted["summary_line"]
    assert "`1` reintento(s) del cliente" in formatted["summary_line"]
    assert "eventos del cliente" in formatted["summary_line"]
    assert "2 resp. exitosas (1 fallo(s), 1 reintento(s))" in formatted["by_agent_line"]


def test_orchestrator_total_12_successful_calls_with_evaluador_retry_and_26180_tokens(monkeypatch):
    """
    Reproduce el escenario completo de los 5 agentes con 12 respuestas exitosas
    (Orquestador 5, Preparador 2, Analizador Mensajes 2, Analizador Enlaces 1, Evaluador 2)
    donde el segundo turno del Evaluador sufre un error de red transitorio y reintenta con éxito,
    sumando exactamente 26.180 tokens (24.996 entrada + 1.184 salida) y conservando el fallo sin cero.
    """
    monkeypatch.setattr(time, "sleep", lambda _secs: None)

    def _wrap_usage(inner_client: ScriptedMockLLMClient, usage_seq: List[Any]):
        orig_gen = inner_client.models.generate_content
        idx = {"i": 0}

        def wrapped_gen(model: str, contents: Any, config: Any):
            u = usage_seq[idx["i"]]
            idx["i"] += 1
            if isinstance(u, Exception):
                raise u
            resp = orig_gen(model, contents, config)
            resp.usage_metadata = u
            return resp

        inner_client.models.generate_content = wrapped_gen  # type: ignore[method-assign]
        return inner_client

    orq_client = _wrap_usage(
        make_standard_orquestador_mock_client("text"),
        [
            DummyUsageMetadata(1000, 50, 1050),
            DummyUsageMetadata(1200, 60, 1260),
            DummyUsageMetadata(1400, 70, 1470),
            DummyUsageMetadata(1600, 80, 1680),
            DummyUsageMetadata(1800, 90, 1890),
        ],
    )
    def _prep_step(contents: Any, config: Any) -> MockLLMResponse:
        if len(contents) == 1:
            return MockLLMResponse(
                function_calls=[
                    MockFunctionCall("tool_validar_entrada", {"input_mode": "text"}),
                    MockFunctionCall("tool_extraer_enlaces", {"include_static_metadata": True}),
                ]
            )
        return MockLLMResponse(text="Preparación completada satisfactoriamente.")

    prep_client = _wrap_usage(
        ScriptedMockLLMClient(_prep_step),
        [
            DummyUsageMetadata(2000, 100, 2100),
            DummyUsageMetadata(2200, 110, 2310),
        ],
    )
    msg_client = _wrap_usage(
        make_standard_analizador_mensajes_mock_client(parallel_in_one_turn=True),
        [
            DummyUsageMetadata(3000, 150, 3150),
            DummyUsageMetadata(3200, 160, 3360),
        ],
    )
    url_client = _wrap_usage(
        make_standard_analizador_enlaces_mock_client(["URL-1"]),
        [
            DummyUsageMetadata(1500, 64, 1564),
        ],
    )

    # Evaluador: 1° turno OK (3000+120=3120), 2° turno intento fallido por error transitorio 503,
    # 2° turno reintento OK (3096+130=3226). Total: 2 respuestas exitosas, 1 fallo, 1 reintento.
    # Totales entrada: 7000 + 4200 + 6200 + 1500 + 6096 = 24996
    # Totales salida:   350 +  210 +  310 +   64 +  250 =  1184
    # Total general:   26180
    def _eval_step(contents: Any, config: Any) -> MockLLMResponse:
        if len(contents) == 1:
            return MockLLMResponse(
                function_calls=[
                    MockFunctionCall("tool_reunir_hallazgos", {"confirm_session": True}),
                    MockFunctionCall("tool_calcular_puntaje", {"confirm_gathered": True}),
                    MockFunctionCall("tool_asignar_nivel_riesgo", {"confirm_scored": True}),
                    MockFunctionCall("tool_explicar_resultado", {"confirm_level_assigned": True}),
                    MockFunctionCall("tool_recomendar_cuidados", {"confirm_level_assigned": True}),
                ]
            )
        return MockLLMResponse(text="Evaluación final completada tras reintento.")

    eval_client = _wrap_usage(
        ScriptedMockLLMClient(_eval_step),
        [
            DummyUsageMetadata(3000, 120, 3120),
            RuntimeError("503 UNAVAILABLE: Temporary backend error"),
            DummyUsageMetadata(3096, 130, 3226),
        ],
    )

    orq = OrquestadorAgent(
        orquestador_llm_client=orq_client,
        preparador_llm_client=prep_client,
        analizador_mensajes_llm_client=msg_client,
        analizador_enlaces_llm_client=url_client,
        evaluador_llm_client=eval_client,
    )
    resp = orq.run(
        AgentInputRequest(
            input_mode="text",
            text_content="Su cuenta será bloqueada en 2 horas. Ingrese a https://ejemplo-neutro.com y valide su clave.",
        )
    )
    assert resp.status == "success"
    u = resp.usage_metrics
    assert u["llm_successful_calls_total"] == 12
    assert u["llm_calls_total"] == 12
    assert u["llm_failed_attempts_total"] == 1
    assert u["llm_retries_total"] == 1
    assert u["llm_total_attempts"] == 13
    assert u["by_agent"]["orquestador"]["llm_successful_calls"] == 5
    assert u["by_agent"]["preparador"]["llm_successful_calls"] == 2
    assert u["by_agent"]["analizador_mensajes"]["llm_successful_calls"] == 2
    assert u["by_agent"]["analizador_enlaces"]["llm_successful_calls"] == 1
    assert u["by_agent"]["evaluador"]["llm_successful_calls"] == 2
    assert u["by_agent"]["evaluador"]["llm_failed_attempts"] == 1
    assert u["by_agent"]["evaluador"]["llm_retries"] == 1
    assert u["prompt_tokens_total"] == 24996
    assert u["output_tokens_total"] == 1184
    assert u["total_tokens"] == 26180
    assert u["coverage"]["status"] == "partial"


def test_explanation_never_claims_fake_page_when_url_has_no_signals():
    """
    Verifica que ante amenaza de bloqueo + urgencia + pedido de claves + URL sin señales
    (`analizado_sin_senales`), la explicación NO afirme que la página es falsa y describa
    únicamente las señales observadas, conservando riesgo ALTO y puntaje exacto.
    """
    msg = (
        "Su cuenta será bloqueada en las próximas horas. "
        "Ingrese en https://portal-ejemplo.com para confirmar su contraseña y token."
    )
    local_report = run_pipeline(msg)
    assert local_report["risk_assessment"]["level"] == "ALTO"
    expected_score = local_report["risk_assessment"]["score"]
    assert expected_score >= 50
    # URL sin señales sintácticas de riesgo
    assert len(local_report["url_analysis"]) == 1
    assert local_report["url_analysis"][0]["is_ip_address"] is False
    assert local_report["url_analysis"][0]["has_punycode"] is False

    exp = local_report["non_technical_explanation"]
    assert "página falsa" not in exp.lower()
    assert "amenaza de bloqueo" in exp.lower()
    assert "presión de tiempo" in exp.lower()
    assert "enlace" in exp.lower()
    assert "claves o códigos de seguridad" in exp.lower()

    # Consistencia en Markdown
    md_report = ReportGenerator().generate_human_readable_report(local_report)
    assert "página falsa" not in md_report.lower()
    assert exp in md_report

    # Consistencia en Orquesta simulada + PDF
    orq = OrquestadorAgent(
        orquestador_llm_client=make_standard_orquestador_mock_client("text"),
        preparador_llm_client=make_standard_preparador_mock_client("text"),
        analizador_mensajes_llm_client=make_standard_analizador_mensajes_mock_client(True),
        analizador_enlaces_llm_client=make_standard_analizador_enlaces_mock_client(["URL-1"]),
        evaluador_llm_client=make_standard_evaluador_mock_client(generate_pdf=True),
    )
    orch_resp = orq.run(AgentInputRequest(input_mode="text", text_content=msg))
    assert orch_resp.status == "success"
    assert orch_resp.evaluation is not None
    assert orch_resp.evaluation.nivel_riesgo == "ALTO"
    assert orch_resp.evaluation.puntaje == expected_score
    assert "página falsa" not in orch_resp.evaluation.explicacion_no_tecnica.lower()
    assert orch_resp.evaluation.explicacion_no_tecnica == exp

    pdf_bytes = generate_pdf_report(orch_resp.report)
    assert pdf_bytes.startswith(b"%PDF-")

    # Incluso cuando la URL sí tiene señales sintácticas, no se afirma "página falsa" ni autenticidad verificable
    url_sig_exp = ReportGenerator().build_non_technical_explanation(
        risk_level="ALTO",
        indicators=[],
        url_analyses=[{"raw_url": "http://192.168.10.25/validar", "is_ip_address": True, "findings": ["IP en host"], "status": "analizado_con_senales"}],
        prompt_injection=False,
    ).lower()
    assert "página falsa" not in url_sig_exp
    assert "no corresponden a un sitio oficial" not in url_sig_exp
    assert "no verifica ni descarta" in url_sig_exp


def test_limitations_accurately_distinguish_local_vs_orchestrated_and_static_urls():
    """
    Verifica que:
    - Modo local reporte ejecución local sin red, análisis estático de URLs y OCR local.
    - Modo orquesta indique el uso de la API externa de Gemini, análisis estático de URLs y OCR local.
    - La lista compartida `ReportGenerator.LIMITATIONS` sea válida para ambos modos sin afirmar
      globalmente 'no se realizaron peticiones de red'.
    """
    msg = "Su cuenta será bloqueada en 2 horas. Ingrese a https://portal-ejemplo.com y valide su clave."

    # 1. Modo local determinístico
    local_rep = analyze_text(msg, input_mode="text")
    local_lims = " | ".join(local_rep["limitations"]).lower()
    assert "sin conexión de red" in local_lims
    assert "estático" in local_lims and "dns" in local_lims and "whois" in local_lims
    assert "ocr" in local_lims and "localmente" in local_lims
    assert "api externa de gemini" not in local_lims

    # 2. Modo orquesta de agentes
    orq = OrquestadorAgent(
        orquestador_llm_client=make_standard_orquestador_mock_client("text"),
        preparador_llm_client=make_standard_preparador_mock_client("text"),
        analizador_mensajes_llm_client=make_standard_analizador_mensajes_mock_client(True),
        analizador_enlaces_llm_client=make_standard_analizador_enlaces_mock_client(["URL-1"]),
        evaluador_llm_client=make_standard_evaluador_mock_client(generate_pdf=False),
    )
    orch_resp = orq.run(AgentInputRequest(input_mode="text", text_content=msg))
    orch_lims = " | ".join(orch_resp.report["limitations"]).lower()
    assert "api externa de gemini" in orch_lims
    assert "ocultamiento preventivo" in orch_lims and "sin garantizar" in orch_lims
    assert "estático" in orch_lims and "dns" in orch_lims and "whois" in orch_lims
    assert "ocr" in orch_lims and "localmente" in orch_lims
    assert "no se realizaron peticiones de red" not in orch_lims

    # 3. Redacción compartida
    shared_lims = " | ".join(ReportGenerator.LIMITATIONS).lower()
    assert "no se realizaron peticiones de red" not in shared_lims
    assert "modo local determinístico" in shared_lims
    assert "api externa de gemini" in shared_lims
    assert "estático" in shared_lims and "ocr" in shared_lims
