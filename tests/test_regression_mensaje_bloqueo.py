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


def test_threat_detection_negation_and_advisory_context_limits():
    """
    Verifica el comportamiento de detección de amenazas ante:
    - Negaciones explícitas ("Su cuenta no va a ser bloqueada", "No vamos a bloquear su cuenta").
    - Mensajes de consejo o advertencia que citan frases de phishing ("Consejo: si recibís 'su cuenta va a ser bloqueada', no respondas").
    Documenta la limitación intrínseca de contexto: citas textuales son reconocidas como señuelo.
    """
    analyzer = TextAnalyzer(load_policy())

    # 1. Negación con 'no' entre sujeto y perífrasis pasiva
    det_neg1, snips1 = analyzer._detect_blocking_threats("Su cuenta no va a ser bloqueada.")
    assert det_neg1 is False
    assert len(snips1) == 0

    # 2. Negación directa con 'no' antes del verbo activo
    det_neg2, snips2 = analyzer._detect_blocking_threats("No vamos a bloquear su cuenta.")
    assert det_neg2 is False
    assert len(snips2) == 0

    det_neg3, snips3 = analyzer._detect_blocking_threats("Nunca suspenderemos su servicio de banca móvil.")
    assert det_neg3 is False
    assert len(snips3) == 0

    # 3. Contexto de consejo/informativo que cita una amenaza:
    # Por diseño defensivo, la frase maliciosa citada es detectada como patrón textual sospechoso,
    # ya que descartar comillas universalmente permitiría evasiones de phishing entrecomillado.
    det_adv, snips_adv = analyzer._detect_blocking_threats(
        "Consejo de seguridad: si recibís 'su cuenta va a ser bloqueada', no respondas ni ingreses."
    )
    assert det_adv is True
    assert any("cuenta va a ser bloqueada" in s.lower() for s in snips_adv)


def test_url_extraction_edge_cases_and_catalog_boundaries():
    """
    Verifica la extracción de dominios sin protocolo ante:
    - Correos electrónicos (no deben extraerse como enlaces de navegación).
    - Puntuación al final de una oración (debe recortarse limpiamente).
    - URLs con parámetros de consulta y fragmentos (deben conservarse completos).
    - Dominios con TLD fuera del catálogo (no deben coincidir parcialmente ni extraerse sin esquema).
    """
    # 1. Correos electrónicos
    assert extract_urls("Escribinos a soporte@banco.com para más información.") == []
    assert extract_urls("Contacto oficial: juan.perez@empresa.com.ar.") == []

    # 2. Puntuación al final de la oración
    res_punct = extract_urls("Ingrese a bbva.com.ar. No demore.")
    assert res_punct == ["http://bbva.com.ar"]

    res_comma = extract_urls("Visite misitio.online, antes de las 18.")
    assert res_comma == ["http://misitio.online"]

    # 3. URLs con parámetros y fragmentos
    res_params = extract_urls("bbva.com/login?user=123&token=abc#seccion")
    assert res_params == ["http://bbva.com/login?user=123&token=abc#seccion"]

    # 4. Dominios con TLD fuera del catálogo
    # Sin esquema ni www: no se extraen para evitar falsos positivos
    assert extract_urls("Visite portal.internal para gestionar.") == []
    assert extract_urls("Sitio falso en banco.tienda urgente.") == []

    # Con www o esquema explícito: sí se extraen aunque el TLD no esté en el catálogo de schemeless
    res_www = extract_urls("Consulte www.museo.museum para detalles.")
    assert res_www == ["http://www.museo.museum"]

    res_https = extract_urls("Sitio en https://banco.tienda para compras.")
    assert res_https == ["https://banco.tienda"]


def test_low_risk_with_isolated_signals_explanation_coherence():
    """
    Verifica que cuando un texto recibe puntaje bajo pero contiene alguna señal aislada
    (ej. únicamente urgencia artificial = 15 pts < umbral medio de 20 pts),
    la explicación no técnica reconozca el hallazgo y no afirme falsamente
    que no se detectaron señales.
    """
    text_only_urgency = "Estimado cliente, por favor responder en las proximas horas para coordinar la reunión."
    report = analyze_text(text_only_urgency, input_mode="text")

    risk = report["risk_assessment"]
    assert risk["level"] == "BAJO"
    assert risk["score"] == 15
    assert any("REGLA-ING-02" in r for r in risk["activated_rules"])

    # La explicación debe reconocer la señal y su alcance, sin negar su existencia
    explanation = report["non_technical_explanation"]
    assert "No encontramos en el texto las frases típicas" not in explanation
    assert "apuro o urgencia temporal" in explanation
    assert "Riesgo Bajo" in explanation

