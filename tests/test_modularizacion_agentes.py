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


# =============================================================================
# 2. AnalizadorMensajesAgent
# =============================================================================

PRE_TASK6_MSG_ANALYZER_SYSTEM_CHARS = 12205
PRE_TASK6_MSG_ANALYZER_SYSTEM_BYTES = 12355


def test_analizador_mensajes_modular_exports_and_prompt_builder():
    """Verifica re-exportaciones, declaraciones uniformes y sanitización del prompt."""
    from agents.analizador_mensajes.agent import (
        ANALIZADOR_MENSAJES_AGENT_NAME,
        ANALIZADOR_MENSAJES_ALLOWED_SKILLS,
        ANALIZADOR_MENSAJES_ALLOWED_TOOLS,
        ANALIZADOR_MENSAJES_BASE_INSTRUCTIONS,
        ANALIZADOR_MENSAJES_TOOL_DECLARATIONS,
        AnalizadorMensajesAgent,
    )
    from agents.analizador_mensajes.prompts import build_untrusted_message_prompt

    assert ANALIZADOR_MENSAJES_AGENT_NAME == "analizador_mensajes"
    assert len(ANALIZADOR_MENSAJES_ALLOWED_SKILLS) == 5
    assert len(ANALIZADOR_MENSAJES_ALLOWED_TOOLS) == 5
    assert len(ANALIZADOR_MENSAJES_TOOL_DECLARATIONS) == 5
    assert "<untrusted_message>" in ANALIZADOR_MENSAJES_BASE_INSTRUCTIONS

    prompt = build_untrusted_message_prompt(42, "Texto [REDACTED] de prueba")
    assert "42 caracteres" in prompt
    assert "<untrusted_message>" in prompt
    assert "Texto [REDACTED] de prueba" in prompt


def test_analizador_mensajes_system_instruction_concise_and_complete():
    """Verifica reducción de build_system_instruction() conservando las 5 skills y reglas."""
    from agents.analizador_mensajes.agent import (
        ANALIZADOR_MENSAJES_ALLOWED_SKILLS,
        AnalizadorMensajesAgent,
    )

    agent = AnalizadorMensajesAgent()
    sys_inst = agent.build_system_instruction()

    assert len(sys_inst) < PRE_TASK6_MSG_ANALYZER_SYSTEM_CHARS
    assert len(sys_inst.encode("utf-8")) < PRE_TASK6_MSG_ANALYZER_SYSTEM_BYTES
    for skill_name in ANALIZADOR_MENSAJES_ALLOWED_SKILLS:
        assert skill_name in sys_inst
    assert "confirm_session_text=true" in sys_inst


def test_analizador_mensajes_result_builder_incomplete_and_complete():
    """Verifica que build_validated_message_analysis_result nunca marque correcto si falta una categoría."""
    from agents.analizador_mensajes.agent import ANALIZADOR_MENSAJES_ALLOWED_SKILLS
    from agents.analizador_mensajes.result_builder import build_validated_message_analysis_result
    from agents.tools.message_analysis_tools import MessageAnalysisSessionState
    from agents.common.contracts import REQUIRED_MESSAGE_ANALYSIS_CATEGORIES

    ctx = PreparationSessionContext(
        input_mode="text",
        validation_done=True,
        is_input_valid=True,
        raw_active_text="Mensaje de prueba normal.",
    )
    skills = list(ANALIZADOR_MENSAJES_ALLOWED_SKILLS)

    # Faltan categorías -> incompleto
    partial_state = MessageAnalysisSessionState()
    partial_state.register_category_review("urgencia", [], ctx.raw_active_text)
    res_inc = build_validated_message_analysis_result(ctx, partial_state, skills)
    assert res_inc.estado == "incompleto"
    assert len(res_inc.categorias_no_revisadas) == 4

    # 5/5 categorías revisadas -> correcto
    full_state = MessageAnalysisSessionState()
    for cat in REQUIRED_MESSAGE_ANALYSIS_CATEGORIES:
        full_state.register_category_review(cat, [], ctx.raw_active_text)
    res_ok = build_validated_message_analysis_result(ctx, full_state, skills)
    assert res_ok.estado == "correcto"
    assert res_ok.categorias_no_revisadas == []


# =============================================================================
# 3. EvaluadorAgent
# =============================================================================

PRE_TASK6_EVALUADOR_SYSTEM_CHARS = 21707
PRE_TASK6_EVALUADOR_SYSTEM_BYTES = 21986


def test_evaluador_modular_exports_and_prompt_builder():
    """Verifica re-exportaciones, mapa de prioridades y prompt condicional de PDF."""
    from agents.evaluador.agent import (
        EVALUADOR_AGENT_NAME,
        EVALUADOR_ALLOWED_SKILLS,
        EVALUADOR_ALLOWED_TOOLS,
        EVALUADOR_BASE_INSTRUCTIONS,
        EVALUADOR_TOOL_DECLARATIONS,
        EVALUADOR_TOOL_ORDER_PRIORITY,
        EvaluadorAgent,
    )
    from agents.evaluador.prompts import build_evaluador_user_prompt
    from agents.common.contracts import MessageAnalysisResult, PreparationResult

    assert EVALUADOR_AGENT_NAME == "evaluador"
    assert len(EVALUADOR_ALLOWED_SKILLS) == 6
    assert len(EVALUADOR_ALLOWED_TOOLS) == 6
    assert len(EVALUADOR_TOOL_DECLARATIONS) == 6
    assert EVALUADOR_TOOL_ORDER_PRIORITY["tool_reunir_hallazgos"] < EVALUADOR_TOOL_ORDER_PRIORITY["tool_generar_pdf"]
    assert "NUNCA calcules" in EVALUADOR_BASE_INSTRUCTIONS

    prep_ok = PreparationResult(
        estado="correcto",
        detalle_estado="sin_enlaces",
        texto_extraido_o_recibido="Texto de ejemplo suficientemente largo para probar.",
        modalidad_entrada="text",
    )
    msg_ok = MessageAnalysisResult(
        estado="correcto",
        categorias_revisadas=["urgencia", "amenazas", "premios", "pedidos_datos", "pedidos_dinero"],
        categorias_sin_hallazgos=["urgencia", "amenazas", "premios", "pedidos_datos", "pedidos_dinero"],
        categorias_no_revisadas=[],
    )

    p_no_pdf = build_evaluador_user_prompt("text", prep_ok, msg_ok, None, generate_pdf=False, save_pdf_to_output=False)
    assert "omití `tool_generar_pdf`" in p_no_pdf

    p_with_pdf = build_evaluador_user_prompt("text", prep_ok, msg_ok, None, generate_pdf=True, save_pdf_to_output=True)
    assert "ejecutá también `tool_generar_pdf` con save_to_output=true" in p_with_pdf


def test_evaluador_system_instruction_concise_and_complete():
    """Verifica reducción sustancial de build_system_instruction() conservando las 6 skills y salvaguardas."""
    from agents.evaluador.agent import EVALUADOR_ALLOWED_SKILLS, EvaluadorAgent

    agent = EvaluadorAgent()
    sys_inst = agent.build_system_instruction()

    assert len(sys_inst) < PRE_TASK6_EVALUADOR_SYSTEM_CHARS
    assert len(sys_inst.encode("utf-8")) < PRE_TASK6_EVALUADOR_SYSTEM_BYTES
    for skill_name in EVALUADOR_ALLOWED_SKILLS:
        assert skill_name in sys_inst
    assert "RIESGO BAJO" in sys_inst
    assert "ReportLab" in sys_inst or "bytes binarios" in sys_inst


def test_evaluador_result_builder_safeguards():
    """Verifica que etapas previas incompletas o con error siempre fuercen INDETERMINADO (nunca BAJO)."""
    from agents.evaluador.agent import EVALUADOR_ALLOWED_SKILLS
    from agents.evaluador.result_builder import build_validated_evaluation_result
    from agents.tools.evaluation_tools import EvaluationSessionState
    from agents.common.contracts import MessageAnalysisResult, PreparationResult

    skills = list(EVALUADOR_ALLOWED_SKILLS)
    prep_inc = PreparationResult(
        estado="incompleto",
        detalle_estado="texto_no_extraible",
        texto_extraido_o_recibido="",
        modalidad_entrada="ocr_screenshot",
        mensaje_error="Imagen ilegible",
    )
    msg_dummy = MessageAnalysisResult(
        estado="incompleto",
        categorias_revisadas=[],
        categorias_sin_hallazgos=[],
        categorias_no_revisadas=["urgencia", "amenazas", "premios", "pedidos_datos", "pedidos_dinero"],
    )
    state = EvaluationSessionState(
        raw_text="",
        input_mode="ocr_screenshot",
        prep_res=prep_inc,
        msg_res=msg_dummy,
        url_res=None,
    )
    res = build_validated_evaluation_result(state, prep_inc, msg_dummy, None, skills)
    assert res.estado == "incompleto"
    assert res.nivel_riesgo == "INDETERMINADO"
    assert res.puntaje == 0
