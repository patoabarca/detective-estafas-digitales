"""
Pruebas Unitarias de Medición de Contexto Efectivamente Enviado (Sin Red).

Verifica:
- Serialización canónica determinística de componentes.
- Medición exacta en caracteres y bytes UTF-8 (diferenciados de tokens y tráfico de red).
- Tratamiento de respuestas de herramientas como desglose sin duplicación en el total.
- Captura de instantáneas de contexto por turno y por agente.
- Ejecución determinística de los 3 escenarios de la línea base reproducible.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from agents.common.context_metrics import (
    canonical_json_serialize,
    extract_contents_canonical,
    extract_system_instruction_text,
    extract_tool_declarations_canonical,
    extract_tool_responses_breakdown,
    measure_text_size,
    ContextRecordingCollector,
    TurnContextSnapshot,
)
from agents.common.contracts import AgentInputRequest
from scripts.reproduce_context_baseline import (
    MockOCRForBaseline,
    make_dummy_png_bytes,
    run_scenario,
)


def test_canonical_json_serialization_is_deterministic():
    """Verifica que objetos con diferente orden de claves se serialicen de forma idéntica."""
    dict_a = {"z": 1, "a": 2, "m": {"c": 3, "b": 4}}
    dict_b = {"a": 2, "m": {"b": 4, "c": 3}, "z": 1}

    ser_a = canonical_json_serialize(dict_a)
    ser_b = canonical_json_serialize(dict_b)

    assert ser_a == ser_b
    assert ser_a == '{"a":2,"m":{"b":4,"c":3},"z":1}'


def test_measure_text_size_chars_and_utf8_bytes():
    """Verifica la distinción entre longitud en caracteres y bytes UTF-8 para caracteres multietapa."""
    # Texto con caracteres acentuados y emoji en español
    sample = "Atención: Verificación de seguridad 🛡️"
    metric = measure_text_size(sample)

    assert metric["chars"] == len(sample)
    assert metric["bytes_utf8"] == len(sample.encode("utf-8"))
    # El emoji y las tildes ocupan más bytes que caracteres
    assert metric["bytes_utf8"] > metric["chars"]


def test_tool_responses_breakdown_not_duplicated_in_total():
    """
    Verifica que las respuestas de herramientas (function_response) se reporten
    como un desglose informativo y NO se vuelvan a sumar al total de la solicitud
    (dado que ya están contenidas en contents).
    """
    collector = ContextRecordingCollector()
    sys_inst = "Sos un agente auditor"
    tools_config = [
        {"name": "tool_test", "description": "Herramienta de prueba", "parameters": {}}
    ]
    # Historial con llamada de función y respuesta de herramienta
    contents = [
        {"role": "user", "parts": [{"text": "Analizar URL"}]},
        {"role": "model", "parts": [{"function_call": {"name": "tool_test", "args": {"url": "http://ejemplo.com"}}}]},
        {"role": "user", "parts": [{"function_response": {"name": "tool_test", "response": {"result": {"status": "ok"}}}}]},
    ]

    snap = collector.record_turn(
        agent="test_agent",
        model="gemini-3.5-flash-lite",
        system_instruction_raw=sys_inst,
        config={"system_instruction": sys_inst, "tools": tools_config},
        contents_raw=contents,
    )

    sys_len = snap.system_instruction["chars"]
    tools_len = snap.tool_declarations["chars"]
    contents_len = snap.contents["chars"]
    tool_resp_len = snap.tool_responses_breakdown["chars"]

    # El desglose de respuestas de herramientas debe ser > 0
    assert tool_resp_len > 0
    # La respuesta de herramienta está físicamente dentro del JSON de contents
    assert tool_resp_len < contents_len

    # El total de la solicitud debe ser EXACTAMENTE la suma de los 3 componentes base
    expected_chars = sys_len + tools_len + contents_len
    assert snap.total_request["chars"] == expected_chars
    # NO debe sumarse dos veces tool_resp_len
    assert snap.total_request["chars"] < (expected_chars + tool_resp_len)


def test_baseline_scenario_1_text_without_links():
    """Verifica que el Escenario 1 (texto sin enlaces) omita al Analizador de Enlaces."""
    req = AgentInputRequest(
        input_mode="text",
        text_content="Estimado cliente: su pedido se encuentra listo para retiro presencial en sucursal con DNI.",
    )
    res = run_scenario("TEST-01", "Texto sin enlaces", req)

    assert "analizador_enlaces" not in res["agents_involved"]
    assert set(res["agents_involved"]) == {"orquestador", "preparador", "analizador_mensajes", "evaluador"}
    assert res["total_simulated_turns"] == 14
    # Reducción Tarea 6: depuración de SKILL.md en Preparador, Analizador de Mensajes y Evaluador
    # (antes de Tarea 6 superaba 150000 chars; ahora se acota entre 80000 y 150000).
    assert 80000 < res["accumulated_request_chars"] < 150000


def test_baseline_scenario_2_text_with_two_links():
    """Verifica que el Escenario 2 involucre a los 5 agentes y analice los 2 enlaces."""
    msg = (
        "Alerta Banco Falso: Ingrese a https://banco-seguro-falso.com/login o reclame su premio en "
        "https://promo-aniversario-falsa.xyz/premio para validar sus datos."
    )
    req = AgentInputRequest(input_mode="text", text_content=msg)
    res = run_scenario("TEST-02", "Texto con dos enlaces", req, requested_urls_for_enlaces=["URL-1", "URL-2"])

    assert "analizador_enlaces" in res["agents_involved"]
    assert len(res["agents_involved"]) == 5
    # Optimización Tarea 4: AnalizadorEnlaces finaliza anticipadamente en 1 turno (evita turno de resumen)
    assert res["by_agent"]["analizador_enlaces"]["turns_count"] == 1
    assert res["total_simulated_turns"] == 16


def test_baseline_scenario_3_screenshot_ocr_with_link():
    """Verifica que el Escenario 3 ejecute el turno adicional de OCR en el Preparador."""
    ocr_text = "Intimación: Ingrese a https://portal-deuda-ficticio.online/pagar para regularizar."
    mock_ocr = MockOCRForBaseline(
        text=ocr_text,
        url_warnings=[{"snippet": "portal-deuda-ficticio.online", "explanation": "Dominio .online"}],
    )
    req = AgentInputRequest(
        input_mode="ocr_screenshot",
        image_bytes=make_dummy_png_bytes(),
        image_filename="captura.png",
    )
    res = run_scenario("TEST-03", "Captura OCR", req, ocr_service=mock_ocr, requested_urls_for_enlaces=["URL-1"])

    assert res["input_mode"] == "ocr_screenshot"
    assert res["by_agent"]["preparador"]["turns_count"] == 4
    # Optimización Tarea 4: AnalizadorEnlaces finaliza en 1 turno, reduciendo turnos totales de 18 a 17
    assert res["by_agent"]["analizador_enlaces"]["turns_count"] == 1
    assert res["total_simulated_turns"] == 17
