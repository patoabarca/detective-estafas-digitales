"""
Pruebas de Regresión para el Caso de Mensaje de Bloqueo con Enlace Schemeless.

Verifica:
1. Extracción y normalización de enlaces sin protocolo (schemeless) con TLDs reconocidos y sospechosos (ej. bbvafraces.misitio.online).
2. Detección de amenazas de bloqueo redactadas con perífrasis verbal en futuro ("va a ser bloqueada", "ha sido bloqueada", etc.).
3. Detección de urgencia artificial ("en las proximas horas").
4. Coherencia en la longitud analizada reportada (`input_char_count` > 0 y exactamente igual a la longitud del texto).
5. Coherencia de la explicación no técnica en el informe (no emitir mensaje de ausencia de señales cuando se detectan indicadores).
6. Trazabilidad completa en ambos modos de ejecución: motor determinístico y orquesta de agentes simulada.
"""

from __future__ import annotations

import pytest

from scripts.analyzer import TextAnalyzer
from scripts.url_analyzer import extract_urls, analyze_single_url
from scripts.worker import load_policy
from web.analysis_adapter import analyze_text
from agents.common.contracts import AgentInputRequest
from agents.orquestador.agent import OrquestadorAgent
from tests.test_agents_orchestration import (
    make_standard_orquestador_mock_client,
    make_standard_preparador_mock_client,
    make_standard_analizador_mensajes_mock_client,
    make_standard_analizador_enlaces_mock_client,
    make_standard_evaluador_mock_client,
)

CASE_TEXT = (
    "su cuenta va a ser bloqueada en las proximas horas, "
    "Ingrese al siguiente enlace para evitarlo   bbvafraces.misitio.online"
)


def test_extract_schemeless_url_and_detect_subdomain_and_tld_signals():
    """
    Verifica que una dirección web sin esquema ni www sea extraída
    y que la auditoría estática identifique el subdominio engañoso y el TLD sospechoso.
    """
    urls = extract_urls(CASE_TEXT)
    assert len(urls) == 1
    assert "bbvafraces.misitio.online" in urls[0]
    # Comprobar normalización para análisis sintáctico
    assert urls[0].startswith("http://") or urls[0].startswith("https://")

    # Auditoría estática sin red
    audit = analyze_single_url(urls[0])
    assert audit["domain"] == "bbvafraces.misitio.online"
    findings_text = " ".join(audit["findings"])
    assert "bbva" in findings_text.lower()
    assert ".online" in findings_text.lower()


def test_detect_periphrastic_future_blocking_threats():
    """
    Verifica que amenazas expresadas mediante perífrasis verbales pasivas
    ('va a ser bloqueada', 'van a ser suspendidas', 'ha sido bloqueada')
    sean reconocidas por el detector de amenazas de bloqueo (ING-AMENAZA-BLOQUEO).
    """
    analyzer = TextAnalyzer(load_policy())

    # Caso en estudio
    detected, snippets = analyzer._detect_blocking_threats(CASE_TEXT)
    assert detected is True
    assert any("cuenta va a ser bloqueada" in s.lower() for s in snippets)

    # Variaciones de perífrasis y tiempos compuestos
    var1 = "Aviso: su cuenta ha sido bloqueada por seguridad."
    det1, snips1 = analyzer._detect_blocking_threats(var1)
    assert det1 is True
    assert any("cuenta ha sido bloqueada" in s.lower() for s in snips1)

    var2 = "Informamos que sus tarjetas van a ser canceladas hoy."
    det2, snips2 = analyzer._detect_blocking_threats(var2)
    assert det2 is True

    var3 = "Su acceso fue suspendido por actividad sospechosa."
    det3, snips3 = analyzer._detect_blocking_threats(var3)
    assert det3 is True


def test_deterministic_pipeline_case_coherence_and_char_count():
    """
    Verifica que el modo determinístico procese el texto completo, compute
    los caracteres analizados con exactitud, identifique las reglas activadas
    y emita una explicación congruente con el nivel de riesgo.
    """
    report = analyze_text(CASE_TEXT, input_mode="text")

    # 1. Caracteres analizados nunca deben ser 0 para texto no vacío
    assert report["input_char_count"] == len(CASE_TEXT)
    assert report["input_mode"] == "text"

    # 2. Indicadores detectados
    ind_ids = [ind["id"] for ind in report.get("indicators_detected", [])]
    assert "ING-AMENAZA-BLOQUEO" in ind_ids
    assert "ING-URGENCIA-ARTIFICIAL" in ind_ids

    # 3. Auditoría de URL
    assert len(report.get("url_analysis", [])) >= 1
    url_audit = report["url_analysis"][0]
    assert "bbvafraces.misitio.online" in url_audit["domain"]

    # 4. Clasificación de riesgo
    risk = report.get("risk_assessment", {})
    rules = risk.get("activated_rules", [])
    assert any("REGLA-ING-01" in r for r in rules)  # Amenaza (+35)
    assert any("REGLA-ING-02" in r for r in rules)  # Urgencia (+15)
    assert any("REGLA-URL-02" in r for r in rules)  # Subdominio engañoso (+30)

    # Nivel de riesgo ALTO por superación de umbral y combinación crítica (amenaza + url engañosa)
    assert risk.get("level") == "ALTO"
    assert risk.get("score") >= 50

    # 5. Explicación no técnica congruente (no debe afirmar ausencia de señales)
    explanation = report.get("non_technical_explanation", "")
    assert "No encontramos en el texto las frases típicas" not in explanation
    assert "RIESGO ALTO" in explanation


def test_agent_orchestrated_pipeline_case_coherence_and_char_count():
    """
    Verifica que la orquesta de agentes en simulación completa delegue
    a los especialistas correspondientes, conserve la longitud en caracteres
    en el informe final (nunca 0) y clasifique el riesgo coherentemente.
    """
    orq = OrquestadorAgent(
        orquestador_llm_client=make_standard_orquestador_mock_client("text"),
        preparador_llm_client=make_standard_preparador_mock_client("text"),
        analizador_mensajes_llm_client=make_standard_analizador_mensajes_mock_client(parallel_in_one_turn=True),
        analizador_enlaces_llm_client=make_standard_analizador_enlaces_mock_client(["URL-1"]),
        evaluador_llm_client=make_standard_evaluador_mock_client(),
    )
    req = AgentInputRequest(input_mode="text", text_content=CASE_TEXT)
    resp = orq.run(req)

    assert resp.status == "success"

    # Preparación
    assert resp.preparation is not None
    assert resp.preparation.estado == "correcto"
    assert len(resp.preparation.enlaces_encontrados) == 1
    assert "bbvafraces.misitio.online" in resp.preparation.enlaces_encontrados[0]

    # Análisis de Mensaje
    assert resp.message_analysis is not None
    assert resp.message_analysis.estado == "correcto"
    msg_signal_ids = [s.id_senal for s in resp.message_analysis.senales_encontradas]
    assert "ING-AMENAZA-BLOQUEO" in msg_signal_ids
    assert "ING-URGENCIA-ARTIFICIAL" in msg_signal_ids

    # Análisis de Enlaces
    assert resp.url_analysis is not None
    assert resp.url_analysis.intervino_agente is True
    assert resp.url_analysis.estado == "correcto"
    assert len(resp.url_analysis.enlaces_analizados) == 1
    assert resp.url_analysis.enlaces_analizados[0].domain == "bbvafraces.misitio.online"

    # Evaluación
    assert resp.evaluation is not None
    assert resp.evaluation.nivel_riesgo == "ALTO"
    assert resp.evaluation.puntaje >= 50
    eval_rules = resp.evaluation.reglas_activadas
    assert any("REGLA-ING-01" in r for r in eval_rules)
    assert any("REGLA-ING-02" in r for r in eval_rules)
    assert any("REGLA-URL-02" in r for r in eval_rules)

    # Informe final adaptado a la aplicación (to_engine_report)
    final_report = resp.report
    assert final_report is not None
    assert final_report.get("input_char_count") == len(CASE_TEXT)
    assert final_report.get("input_mode") == "text"
    assert final_report.get("risk_assessment", {}).get("level") == "ALTO"

    explanation = final_report.get("non_technical_explanation", "")
    assert "No encontramos en el texto las frases típicas" not in explanation
