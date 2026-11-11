"""
Pruebas de Modularización de Agentes y Revisión de Skills (Tarea 6).

Verifica sin dependencias de red ni Git:
- Separación de responsabilidades en `prompts.py`, `result_builder.py` y `agent.py`
  preservando exactamente las exportaciones públicas y contratos previos.
- Integridad y suficiencia de `build_system_instruction()` junto con su reducción
  de tamaño respecto de la base previa (commit c800c45).
"""

from __future__ import annotations

from agents.preparador.agent import (
    PREPARADOR_AGENT_NAME,
    PREPARADOR_ALLOWED_SKILLS,
    PREPARADOR_ALLOWED_TOOLS,
    PREPARADOR_BASE_INSTRUCTIONS,
    PREPARADOR_TOOL_DECLARATIONS,
    PREPARADOR_TOOL_ORDER_PRIORITY,
    PreparadorAgent,
)
from agents.preparador.prompts import build_preparador_user_prompt
from agents.preparador.result_builder import build_validated_preparation_result
from agents.tools.preparation_tools import PreparationSessionContext


# =============================================================================
# 1. PreparadorAgent
# =============================================================================

PRE_TASK6_PREPARADOR_SYSTEM_CHARS = 9727
PRE_TASK6_PREPARADOR_SYSTEM_BYTES = 9855


def test_preparador_modular_exports_and_prompt_builder():
    """Verifica re-exportaciones en agent.py y construcción de prompt por modalidad."""
    assert PREPARADOR_AGENT_NAME == "preparador"
    assert len(PREPARADOR_ALLOWED_SKILLS) == 3
    assert len(PREPARADOR_ALLOWED_TOOLS) == 3
    assert len(PREPARADOR_TOOL_DECLARATIONS) == 3
    assert PREPARADOR_TOOL_ORDER_PRIORITY["tool_validar_entrada"] < PREPARADOR_TOOL_ORDER_PRIORITY["tool_extraer_enlaces"]
    assert "Untrusted Data" in PREPARADOR_BASE_INSTRUCTIONS

    p_text = build_preparador_user_prompt("text")
    assert "input_mode='text'" in p_text
    assert "tool_validar_entrada" in p_text

    p_ocr = build_preparador_user_prompt("ocr_screenshot")
    assert "input_mode='ocr_screenshot'" in p_ocr
    assert "tool_extraer_texto_captura" in p_ocr


def test_preparador_system_instruction_concise_and_complete():
    """Verifica reducción de build_system_instruction() conservando reglas de seguridad y skills."""
    agent = PreparadorAgent()
    sys_inst = agent.build_system_instruction()

    assert len(sys_inst) < PRE_TASK6_PREPARADOR_SYSTEM_CHARS
    assert len(sys_inst.encode("utf-8")) < PRE_TASK6_PREPARADOR_SYSTEM_BYTES
    for skill_name in PREPARADOR_ALLOWED_SKILLS:
        assert skill_name in sys_inst
    assert "Zero Network" in sys_inst
    assert "empty_or_illegible" in sys_inst


def test_preparador_result_builder_all_states():
    """Verifica que build_validated_preparation_result cubra todos los estados contractuales."""
    skills = list(PREPARADOR_ALLOWED_SKILLS)

    # 1. Falta de validación obligatoria
    ctx_no_val = PreparationSessionContext(input_mode="text", raw_input_text="hola")
    r_no_val = build_validated_preparation_result(ctx_no_val, skills)
    assert r_no_val.estado == "error" and r_no_val.detalle_estado == "fallo_herramienta"

    # 2. Entrada inválida
    ctx_inv = PreparationSessionContext(
        input_mode="text",
        validation_done=True,
        is_input_valid=False,
        validation_error_code="EMPTY_TEXT",
        validation_error_message="Texto vacío",
    )
    r_inv = build_validated_preparation_result(ctx_inv, skills)
    assert r_inv.estado == "error" and r_inv.detalle_estado == "entrada_invalida"

    # 3. OCR ilegible -> incompleto (nunca error genérico ni correcto)
    ctx_ocr_empty = PreparationSessionContext(
        input_mode="ocr_screenshot",
        validation_done=True,
        is_input_valid=True,
        ocr_executed=True,
        ocr_status="empty_or_illegible",
        raw_active_text="",
    )
    r_ocr = build_validated_preparation_result(ctx_ocr_empty, skills)
    assert r_ocr.estado == "incompleto" and r_ocr.detalle_estado == "texto_no_extraible"

    # 4. Éxito sin enlaces y con enlaces
    ctx_ok = PreparationSessionContext(
        input_mode="text",
        validation_done=True,
        is_input_valid=True,
        raw_active_text="Mensaje de prueba sin enlaces.",
        extracted_urls=[],
    )
    r_ok_no_links = build_validated_preparation_result(ctx_ok, skills)
    assert r_ok_no_links.estado == "correcto" and r_ok_no_links.detalle_estado == "sin_enlaces"

    ctx_ok.extracted_urls = ["https://ejemplo.test/login"]
    r_ok_links = build_validated_preparation_result(ctx_ok, skills)
    assert r_ok_links.estado == "correcto" and r_ok_links.detalle_estado == "con_enlaces"
