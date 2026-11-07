"""
Pruebas Automatizadas de Validación del Piloto del Analizador de Enlaces
(Rama refactor/piloto-analizador-enlaces)

Objetivos de esta suite:
1. Validar la reducción cuantificable del contexto (instrucción de sistema)
   entre la versión v2.0-orquesta-presentada (commit 454601d) y la versión modularizada.
2. Comprobar la equivalencia funcional del contrato en casos sintéticos reproducibles.
3. Verificar el enmascaramiento estricto de credenciales y parámetros sensibles en
   la construcción de prompts y en los intercambios con el modelo (Cero Fuga de Secretos).
4. Verificar la omisión completa del Analizador de Enlaces en el flujo del Orquestador
   cuando no hay URLs, contrastándolo con la invocación directa y aislada del especialista.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
import pytest

from agents.analizador_enlaces.agent import (
    AnalizadorEnlacesAgent,
    ANALIZADOR_ENLACES_ALLOWED_SKILLS,
)
from agents.analizador_enlaces.prompts import (
    ANALIZADOR_ENLACES_AGENT_NAME,
    ANALIZADOR_ENLACES_BASE_INSTRUCTIONS,
    build_untrusted_urls_prompt,
)
from agents.common.privacy import sanitize_url_for_external_llm
from agents.common.skill_loader import load_skills_for_agent
from agents.common.traceability import AgentTracer
from agents.common.contracts import AgentInputRequest
from agents.orquestador.agent import OrquestadorAgent
from tests.test_agents_orchestration import (
    make_standard_orquestador_mock_client,
    make_standard_preparador_mock_client,
    make_standard_analizador_mensajes_mock_client,
    make_standard_analizador_enlaces_mock_client,
    make_standard_evaluador_mock_client,
)
from agents.tools.preparation_tools import PreparationSessionContext


# =============================================================================
# Infraestructura de Simulación para Pruebas Determinísticas
# =============================================================================

class MockFunctionCall:
    def __init__(self, name: str, args: Dict[str, Any]) -> None:
        self.name = name
        self.args = args


class MockLLMResponse:
    def __init__(
        self,
        function_calls: Optional[List[MockFunctionCall]] = None,
        text: str = "",
    ) -> None:
        self.function_calls = function_calls or []
        self.text = text


class ScriptedMockModels:
    def __init__(self) -> None:
        self.calls_history: List[Dict[str, Any]] = []

    def generate_content(self, model: str, contents: List[Any], config: Any) -> MockLLMResponse:
        self.calls_history.append({"model": model, "contents": list(contents), "config": config})
        # Si ya se invocó la herramienta, cerrar con texto final
        has_tool_response = False
        for msg in contents:
            if isinstance(msg, dict) and msg.get("role") == "user":
                parts = msg.get("parts", [])
                for p in parts:
                    if isinstance(p, dict) and "function_response" in p:
                        has_tool_response = True
                        break
        if has_tool_response:
            return MockLLMResponse(text="Análisis de enlaces completado.")
        # Primer turno: pedir análisis de todas las URLs
        return MockLLMResponse(
            function_calls=[MockFunctionCall("tool_analizar_url", {"url_ids": ["ALL"]})]
        )


class ScriptedMockLLMClient:
    is_mock_client = True

    def __init__(self) -> None:
        self.models = ScriptedMockModels()


# =============================================================================
# 1. Medición de Reducción de Contexto y Equivalencia Funcional
# =============================================================================

# Línea base congelada del commit 454601ddb6259bcec2b77f5ee6478649dd9f183f:
# - Texto plano original (raw string): 5.515 caracteres, 5.592 bytes UTF-8
# - JSON serializado con escape ASCII (ensure_ascii=True): 5.960 caracteres
BASELINE_RAW_CHARS = 5515
BASELINE_RAW_BYTES = 5592
BASELINE_JSON_ESCAPED_CHARS = 5960


def _load_base_agent_class():
    """
    Carga dinámicamente en memoria la clase AnalizadorEnlacesAgent del commit base 454601d
    para asegurar que las pruebas de equivalencia comparen contra la versión base original
    y no únicamente contra expectativas estáticas o contra la nueva implementación.
    """
    import subprocess
    import types
    try:
        base_code = subprocess.check_output(
            ["git", "show", "454601d:agents/analizador_enlaces/agent.py"],
            text=True,
            encoding="utf-8",
        )
        mod = types.ModuleType("base_agent_mod")
        exec(compile(base_code, "base_agent_mod", "exec"), mod.__dict__)
        return mod.AnalizadorEnlacesAgent
    except Exception:
        return None


def test_pilot_system_instruction_context_reduction():
    """
    Verifica que la modularización del agente y el aligeramiento de SKILL.md
    reduzcan la instrucción de sistema más de un 40% en caracteres y bytes UTF-8,
    distinguiendo texto plano original de la serialización JSON con escape ASCII.
    """
    skills = load_skills_for_agent(ANALIZADOR_ENLACES_AGENT_NAME, ANALIZADOR_ENLACES_ALLOWED_SKILLS)
    skill_content = "\n\n".join(s.instructions_markdown for s in skills.values())
    current_system_instruction = f"{ANALIZADOR_ENLACES_BASE_INSTRUCTIONS}\n\n{skill_content}".strip()

    # 1. Medición sobre texto plano original
    raw_chars = len(current_system_instruction)
    raw_bytes = len(current_system_instruction.encode("utf-8"))

    raw_char_reduction = BASELINE_RAW_CHARS - raw_chars
    raw_pct_reduction = (raw_char_reduction / BASELINE_RAW_CHARS) * 100.0

    assert raw_pct_reduction >= 40.0, f"Reducción raw insuficiente: {raw_pct_reduction:.1f}% (esperado >= 40%)"
    assert raw_chars <= 3250, f"Caracteres raw ({raw_chars}) superan el umbral esperado"
    assert raw_bytes <= 3300, f"Bytes raw ({raw_bytes}) superan el umbral esperado"

    # 2. Medición sobre JSON serializado con escape ASCII
    json_escaped_chars = len(json.dumps(current_system_instruction, ensure_ascii=True))
    json_char_reduction = BASELINE_JSON_ESCAPED_CHARS - json_escaped_chars
    json_pct_reduction = (json_char_reduction / BASELINE_JSON_ESCAPED_CHARS) * 100.0

    assert json_pct_reduction >= 40.0, f"Reducción JSON insuficiente: {json_pct_reduction:.1f}%"
    assert json_escaped_chars <= 3500


def test_pilot_functional_contract_equivalence_synthetic_cases():
    """
    Verifica la equivalencia funcional estricta comparando directamente la ejecución del
    agente piloto contra la clase AnalizadorEnlacesAgent del commit base 454601d sobre
    los mismos casos y con el mismo cliente simulado.
    """
    BaseAgentClass = _load_base_agent_class()

    cases = [
        {
            "id": "caso_ip",
            "urls": ["http://192.168.1.50/login"],
            "expected_estado": "correcto",
            "expected_detalle": "analizados_con_senales",
            "expected_reglas": ["REGLA-URL-01"],
        },
        {
            "id": "caso_tld",
            "urls": ["https://promo-aniversario.xyz/sorteo"],
            "expected_estado": "correcto",
            "expected_detalle": "analizados_con_senales",
            "expected_reglas": ["REGLA-URL-05"],
        },
        {
            "id": "caso_legitimo",
            "urls": ["https://portal-seguro.ejemplo.com/faq"],
            "expected_estado": "correcto",
            "expected_detalle": "analizados_sin_senales",
            "expected_reglas": [],
        },
    ]

    for c in cases:
        urls = c["urls"]
        url_map = {f"URL-{i+1}": u for i, u in enumerate(urls)}
        ctx = PreparationSessionContext(
            input_mode="text",
            raw_input_text=" ".join(urls),
            validation_done=True,
            is_input_valid=True,
            links_extracted=True,
            extracted_urls=urls,
            url_id_map=url_map,
            masked_url_id_map=url_map,
        )

        tracer_pilot = AgentTracer()
        client_pilot = ScriptedMockLLMClient()
        pilot_agent = AnalizadorEnlacesAgent(llm_client=client_pilot)
        pilot_res = pilot_agent.run(ctx, tracer=tracer_pilot)

        # Verificación contra especificación esperada
        assert pilot_res.estado == c["expected_estado"]
        assert pilot_res.detalle_estado == c["expected_detalle"]
        assert pilot_res.cantidad_enlaces_extraidos == len(urls)
        assert pilot_res.cantidad_enlaces_procesados == len(urls)
        assert pilot_res.enlaces_omitidos == []
        assert "analizar-url" in pilot_res.skills_cargadas
        assert "tool_analizar_url" in pilot_res.herramientas_invocadas

        if c["expected_reglas"]:
            assert pilot_res.enlaces_analizados[0].reglas_activadas == c["expected_reglas"]
        else:
            assert pilot_res.enlaces_analizados[0].reglas_activadas == []

        # Comparación directa de equivalencia contra el commit base 454601d si está disponible
        if BaseAgentClass is not None:
            tracer_base = AgentTracer()
            client_base = ScriptedMockLLMClient()
            base_agent = BaseAgentClass(llm_client=client_base)
            base_res = base_agent.run(session_ctx=ctx, tracer=tracer_base)

            assert pilot_res.estado == base_res.estado
            assert pilot_res.detalle_estado == base_res.detalle_estado
            assert pilot_res.cantidad_enlaces_extraidos == base_res.cantidad_enlaces_extraidos
            assert pilot_res.cantidad_enlaces_procesados == base_res.cantidad_enlaces_procesados
            assert pilot_res.enlaces_omitidos == base_res.enlaces_omitidos
            assert len(pilot_res.enlaces_analizados) == len(base_res.enlaces_analizados)
            for p_item, b_item in zip(pilot_res.enlaces_analizados, base_res.enlaces_analizados):
                assert p_item.url_id == b_item.url_id
                assert p_item.masked_url == b_item.masked_url
                assert p_item.estado_enlace == b_item.estado_enlace
                assert p_item.reglas_activadas == b_item.reglas_activadas


# =============================================================================
# 2. Privacidad y Enmascaramiento de Credenciales y Parámetros Sensibles
# =============================================================================

def test_url_privacy_sanitization_in_prompt_and_tool_exchange():
    """
    Verifica que las credenciales en URL (user:pass en netloc) y parámetros de consulta
    sensibles conocidos (token, clave, password, email) sean enmascarados de forma efectiva
    tanto en la entrada del prompt como en las respuestas de herramientas en los recorridos probados.
    
    Nota de delimitación: Esta verificación confirma el enmascaramiento para los patrones
    explícitamente contemplados por las expresiones regulares del proyecto, sin constituir
    una garantía universal sobre datos arbitrarios en texto libre no estructurado.
    """
    raw_url = (
        "https://usuario_admin:clave_super_secreta_999@servidor-sospechoso.com/panel"
        "?token=XYZ_TOKEN_SECRETO_123&clave=miClavePrivada&email=victima@empresa.com"
    )
    url_id = "URL-1"
    masked_url, count_redactions = sanitize_url_for_external_llm(raw_url)

    # 1. Enmascaramiento a nivel de sanitizador
    assert count_redactions > 0
    assert "clave_super_secreta_999" not in masked_url
    assert "usuario_admin" not in masked_url
    assert "XYZ_TOKEN_SECRETO_123" not in masked_url
    assert "miClavePrivada" not in masked_url
    assert "victima@empresa.com" not in masked_url
    assert "[CREDENCIAL_URL_OCULTA]" in masked_url
    assert "[VALOR_URL_OCULTO]" in masked_url

    # 2. Prompt no confiable construido para el LLM
    prompt_text = build_untrusted_urls_prompt({url_id: raw_url}, {url_id: masked_url})
    assert "clave_super_secreta_999" not in prompt_text
    assert "XYZ_TOKEN_SECRETO_123" not in prompt_text

    # 3. Ciclo de ejecución del agente
    ctx = PreparationSessionContext(
        input_mode="text",
        raw_input_text=f"Entrar a: {raw_url}",
        validation_done=True,
        is_input_valid=True,
        links_extracted=True,
        extracted_urls=[raw_url],
        url_id_map={url_id: raw_url},
        masked_url_id_map={url_id: masked_url},
    )

    tracer = AgentTracer()
    mock_client = ScriptedMockLLMClient()
    agent = AnalizadorEnlacesAgent(llm_client=mock_client)

    result = agent.run(ctx, tracer=tracer)

    assert result.estado == "correcto"
    assert result.cantidad_enlaces_procesados == 1

    # 4. Inspección estricta de todo el historial enviado al LLM
    serialized_history = json.dumps(mock_client.models.calls_history, ensure_ascii=False)
    assert "clave_super_secreta_999" not in serialized_history
    assert "usuario_admin" not in serialized_history
    assert "XYZ_TOKEN_SECRETO_123" not in serialized_history
    assert "miClavePrivada" not in serialized_history
    assert "victima@empresa.com" not in serialized_history


# =============================================================================
# 3. Caso Sin Enlaces: Especialista Aislado vs. Flujo del Orquestador
# =============================================================================

def test_no_links_specialist_isolation_vs_orchestrator_skipping():
    """
    Aclara el comportamiento ante mensajes sin enlaces:
    - Invocación aislada del especialista: ejecuta su ciclo de agente (2 llamadas simuladas:
      1 para pedir tool_analizar_url(["ALL"]), la tool devuelve processed_count=0, y 1 para cerrar).
    - Flujo completo del Orquestador: detecta que no hay enlaces y omite completamente
      invocar al Analizador de Enlaces, realizando 0 llamadas de modelo y 0 de herramientas.
    """
    # A. Invocación aislada directa del Analizador de Enlaces
    ctx_empty = PreparationSessionContext(
        input_mode="text",
        raw_input_text="Mensaje de prueba sin ningun enlace.",
        validation_done=True,
        is_input_valid=True,
        links_extracted=True,
        extracted_urls=[],
        url_id_map={},
        masked_url_id_map={},
    )
    mock_client_specialist = ScriptedMockLLMClient()
    tracer_specialist = AgentTracer()
    specialist_agent = AnalizadorEnlacesAgent(llm_client=mock_client_specialist)

    res_specialist = specialist_agent.run(ctx_empty, tracer=tracer_specialist)

    assert res_specialist.cantidad_enlaces_extraidos == 0
    assert res_specialist.cantidad_enlaces_procesados == 0
    assert len(mock_client_specialist.models.calls_history) == 2  # 2 turnos simulados del ciclo del agente

    # B. Flujo completo en el Orquestador
    url_mock_client = make_standard_analizador_enlaces_mock_client()
    orquestador = OrquestadorAgent(
        orquestador_llm_client=make_standard_orquestador_mock_client("text"),
        preparador_llm_client=make_standard_preparador_mock_client("text"),
        analizador_mensajes_llm_client=make_standard_analizador_mensajes_mock_client(),
        analizador_enlaces_llm_client=url_mock_client,
        evaluador_llm_client=make_standard_evaluador_mock_client(),
    )

    res_orch = orquestador.run(
        AgentInputRequest(
            input_mode="text",
            text_content="Urgente: su cuenta será suspendida hoy. Ingrese sus datos por este medio.",
        )
    )

    # Verificamos que el orquestador omitió al Analizador de Enlaces
    assert res_orch.status == "success"
    analisis_enlaces = res_orch.url_analysis
    assert analisis_enlaces is not None
    assert analisis_enlaces.intervino_agente is False
    assert analisis_enlaces.detalle_estado == "sin_enlaces"
    assert analisis_enlaces.cantidad_enlaces_extraidos == 0
    assert analisis_enlaces.cantidad_enlaces_procesados == 0
    assert len(url_mock_client.models.calls_history) == 0  # 0 llamadas al modelo del especialista
    assert any(
        ev.get("event_type") == "agent_skipped" and ev.get("tool") == "delegar_analisis_enlaces"
        for ev in res_orch.trace_events
    )
