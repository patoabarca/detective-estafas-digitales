"""
Pruebas Automatizadas de Validación del Piloto del Analizador de Enlaces
(Rama refactor/piloto-analizador-enlaces)

Objetivos de esta suite:
1. Validar la reducción cuantificable del contexto (instrucción de sistema efectiva)
   producida por `build_system_instruction()` entre la versión base v2.0-orquesta-presentada
   (commit 454601d) y la versión modularizada del piloto.
2. Comprobar la equivalencia funcional del contrato en casos sintéticos reproducibles,
   comparando contra los resultados de referencia congelados del commit base 454601d
   de manera 100% independiente de Git (apto para entornos Docker sin historial).
3. Verificar el enmascaramiento estricto de credenciales y parámetros sensibles en
   la construcción de prompts y en los intercambios con el modelo (en los recorridos probados).
4. Verificar la omisión completa del Analizador de Enlaces en el flujo del Orquestador
   cuando no hay URLs, contrastándolo con la invocación directa y aislada del especialista.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
import pytest

from agents.analizador_enlaces.agent import (
    AnalizadorEnlacesAgent,
    ANALIZADOR_ENLACES_AGENT_NAME,
    ANALIZADOR_ENLACES_ALLOWED_SKILLS,
    ANALIZADOR_ENLACES_BASE_INSTRUCTIONS,
)
from agents.analizador_enlaces.prompts import build_untrusted_urls_prompt
from agents.common.contracts import AgentInputRequest
from agents.common.privacy import (
    sanitize_url_component_for_external_llm,
    sanitize_url_for_external_llm,
)
from agents.common.traceability import AgentTracer
from agents.orquestador.agent import OrquestadorAgent
from agents.tools.preparation_tools import PreparationSessionContext
from tests.test_agents_orchestration import (
    make_standard_orquestador_mock_client,
    make_standard_preparador_mock_client,
    make_standard_analizador_mensajes_mock_client,
    make_standard_analizador_enlaces_mock_client,
    make_standard_evaluador_mock_client,
)


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


class CapturingMockModels:
    """Captura copias profundas (deepcopy) de cada solicitud en el momento exacto de la llamada."""
    def __init__(self) -> None:
        self.calls_history: List[Dict[str, Any]] = []

    def generate_content(self, model: str, contents: List[Any], config: Any) -> MockLLMResponse:
        import copy
        self.calls_history.append({
            "model": model,
            "contents": copy.deepcopy(contents),
            "config": copy.deepcopy(config) if config else config,
        })
        has_tool_response = False
        for msg in contents:
            if isinstance(msg, dict) and msg.get("role") == "user":
                for p in msg.get("parts", []):
                    if isinstance(p, dict) and "function_response" in p:
                        has_tool_response = True
                        break
        if has_tool_response:
            return MockLLMResponse(text="Análisis de enlaces completado.")
        return MockLLMResponse(
            function_calls=[MockFunctionCall("tool_analizar_url", {"url_ids": ["ALL"]})]
        )


class CapturingMockLLMClient:
    is_mock_client = True

    def __init__(self) -> None:
        self.models = CapturingMockModels()


# =============================================================================
# 1. Medición Real del Contexto Efectivo de build_system_instruction()
# =============================================================================

# Medición real obtenida de `base_agent.build_system_instruction()` sobre el commit base:
# Commit de origen: 454601ddb6259bcec2b77f5ee6478649dd9f183f
BASELINE_BUILD_SYSTEM_INSTRUCTION_CHARS: int = 5951
BASELINE_BUILD_SYSTEM_INSTRUCTION_BYTES: int = 6036


def test_pilot_system_instruction_context_reduction():
    """
    Verifica que la salida efectiva de build_system_instruction() en el agente piloto
    reduzca el contexto de instrucción más de un 40% en caracteres y bytes UTF-8
    frente a la salida efectiva de build_system_instruction() del commit base 454601d.
    """
    pilot_agent = AnalizadorEnlacesAgent()
    pilot_instruction = pilot_agent.build_system_instruction()

    pilot_chars = len(pilot_instruction)
    pilot_bytes = len(pilot_instruction.encode("utf-8"))

    char_reduction = BASELINE_BUILD_SYSTEM_INSTRUCTION_CHARS - pilot_chars
    char_pct_reduction = (char_reduction / BASELINE_BUILD_SYSTEM_INSTRUCTION_CHARS) * 100.0

    byte_reduction = BASELINE_BUILD_SYSTEM_INSTRUCTION_BYTES - pilot_bytes
    byte_pct_reduction = (byte_reduction / BASELINE_BUILD_SYSTEM_INSTRUCTION_BYTES) * 100.0

    # Verificaciones cuantitativas exactas
    # Actualizado en Tarea 2 (B2): desduplicación de instrucciones entre prompts.py y SKILL.md,
    # y remoción de orden de consulta a archivo local de referencia.
    assert pilot_chars == 2273, f"Caracteres efectivos inesperados: {pilot_chars}"
    assert pilot_bytes == 2304, f"Bytes efectivos inesperados: {pilot_bytes}"
    assert char_reduction == 3678, f"Diferencia de caracteres inesperada: {char_reduction}"
    assert byte_reduction == 3732, f"Diferencia de bytes inesperada: {byte_reduction}"
    assert char_pct_reduction >= 40.0, f"Reducción porcentual insuficiente: {char_pct_reduction:.2f}%"
    assert byte_pct_reduction >= 40.0, f"Reducción porcentual insuficiente: {byte_pct_reduction:.2f}%"


# =============================================================================
# 2. Resultados de Referencia de la Versión Preservada (Commit 454601d)
# =============================================================================

# Commit de origen: 454601ddb6259bcec2b77f5ee6478649dd9f183f
# Procedimiento de regeneración reproducible:
#   Extraer 'agents/analizador_enlaces/agent.py' y '.agents/skills/analizar-url/SKILL.md'
#   desde git show 454601d, instanciar AnalizadorEnlacesAgent con ScriptedMockLLMClient
#   y ejecutar sobre los mismos casos ficticios.
BASELINE_REFERENCE_RESULTS_COMMIT_454601d: Dict[str, Dict[str, Any]] = {
    "caso_ip": {
        "estado": "correcto",
        "detalle_estado": "analizados_con_senales",
        "intervino_agente": True,
        "cantidad_enlaces_extraidos": 1,
        "cantidad_enlaces_procesados": 1,
        "enlaces_omitidos": [],
        "advertencias": [
            "URL [192.168.1.50]: Utiliza HTTP sin cifrado (tráfico legible en texto plano).",
            "URL [192.168.1.50]: El enlace apunta directamente a una dirección IP (192.168.1.50) en lugar de un nombre de dominio legítimo.",
        ],
        "skills_cargadas": ["analizar-url"],
        "herramientas_invocadas": ["tool_analizar_url"],
        "enlaces_analizados": [
            {
                "url_id": "URL-1",
                "masked_url": "http://192.168.1.50/login",
                "estado_enlace": "analizado_con_senales",
                "reglas_activadas": ["REGLA-URL-01"],
            }
        ],
    },
    "caso_tld": {
        "estado": "correcto",
        "detalle_estado": "analizados_con_senales",
        "intervino_agente": True,
        "cantidad_enlaces_extraidos": 1,
        "cantidad_enlaces_procesados": 1,
        "enlaces_omitidos": [],
        "advertencias": [
            "URL [promo-aniversario.xyz]: El dominio utiliza una extensión de dominio de bajo costo frecuentemente asociada a campañas efímeras de spam/phishing (.xyz).",
        ],
        "skills_cargadas": ["analizar-url"],
        "herramientas_invocadas": ["tool_analizar_url"],
        "enlaces_analizados": [
            {
                "url_id": "URL-1",
                "masked_url": "https://promo-aniversario.xyz/sorteo",
                "estado_enlace": "analizado_con_senales",
                "reglas_activadas": ["REGLA-URL-05"],
            }
        ],
    },
    "caso_legitimo": {
        "estado": "correcto",
        "detalle_estado": "analizados_sin_senales",
        "intervino_agente": True,
        "cantidad_enlaces_extraidos": 1,
        "cantidad_enlaces_procesados": 1,
        "enlaces_omitidos": [],
        "advertencias": [
            "La ausencia de señales sintácticas en un enlace NO garantiza que el sitio web sea legítimo o seguro.",
        ],
        "skills_cargadas": ["analizar-url"],
        "herramientas_invocadas": ["tool_analizar_url"],
        "enlaces_analizados": [
            {
                "url_id": "URL-1",
                "masked_url": "https://portal-seguro.ejemplo.com/faq",
                "estado_enlace": "analizado_sin_senales",
                "reglas_activadas": [],
            }
        ],
    },
    "caso_multiples_mixto": {
        "estado": "correcto",
        "detalle_estado": "analizados_con_senales",
        "intervino_agente": True,
        "cantidad_enlaces_extraidos": 2,
        "cantidad_enlaces_procesados": 2,
        "enlaces_omitidos": [],
        "advertencias": [
            "URL [promocion-aniversario.xyz]: El dominio utiliza una extensión de dominio de bajo costo frecuentemente asociada a campañas efímeras de spam/phishing (.xyz).",
            "La ausencia de señales sintácticas en un enlace NO garantiza que el sitio web sea legítimo o seguro.",
        ],
        "skills_cargadas": ["analizar-url"],
        "herramientas_invocadas": ["tool_analizar_url"],
        "enlaces_analizados": [
            {
                "url_id": "URL-1",
                "masked_url": "https://promocion-aniversario.xyz/premio",
                "estado_enlace": "analizado_con_senales",
                "reglas_activadas": ["REGLA-URL-05"],
            },
            {
                "url_id": "URL-2",
                "masked_url": "https://portal-seguro.ejemplo.com/contacto",
                "estado_enlace": "analizado_sin_senales",
                "reglas_activadas": [],
            },
        ],
    },
    "caso_sin_enlaces": {
        "estado": "correcto",
        "detalle_estado": "sin_enlaces",
        "intervino_agente": True,
        "cantidad_enlaces_extraidos": 0,
        "cantidad_enlaces_procesados": 0,
        "enlaces_omitidos": [],
        "advertencias": [],
        "skills_cargadas": ["analizar-url"],
        "herramientas_invocadas": ["tool_analizar_url"],
        "enlaces_analizados": [],
    },
}


def test_pilot_functional_contract_equivalence_synthetic_cases():
    """
    Verifica que el agente piloto produzca resultados idénticos a los resultados
    de referencia obtenidos del commit base 454601d en todos sus campos funcionales,
    sin requerir binarios ni historial de Git en el entorno de ejecución.
    """
    cases_inputs = {
        "caso_ip": ["http://192.168.1.50/login"],
        "caso_tld": ["https://promo-aniversario.xyz/sorteo"],
        "caso_legitimo": ["https://portal-seguro.ejemplo.com/faq"],
        "caso_multiples_mixto": [
            "https://promocion-aniversario.xyz/premio",
            "https://portal-seguro.ejemplo.com/contacto",
        ],
        "caso_sin_enlaces": [],
    }

    for case_id, urls in cases_inputs.items():
        ref = BASELINE_REFERENCE_RESULTS_COMMIT_454601d[case_id]
        url_map = {f"URL-{i+1}": u for i, u in enumerate(urls)}
        ctx = PreparationSessionContext(
            input_mode="text",
            raw_input_text=" ".join(urls) if urls else "Sin enlaces",
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

        # Verificación estricta de equivalencia campo a campo contra referencia base
        assert pilot_res.estado == ref["estado"]
        assert pilot_res.detalle_estado == ref["detalle_estado"]
        assert pilot_res.intervino_agente == ref["intervino_agente"]
        assert pilot_res.cantidad_enlaces_extraidos == ref["cantidad_enlaces_extraidos"]
        assert pilot_res.cantidad_enlaces_procesados == ref["cantidad_enlaces_procesados"]
        assert pilot_res.enlaces_omitidos == ref["enlaces_omitidos"]
        assert pilot_res.advertencias == ref["advertencias"]
        assert pilot_res.skills_cargadas == ref["skills_cargadas"]
        assert pilot_res.herramientas_invocadas == ref["herramientas_invocadas"]
        assert len(pilot_res.enlaces_analizados) == len(ref["enlaces_analizados"])

        for p_item, r_item in zip(pilot_res.enlaces_analizados, ref["enlaces_analizados"]):
            assert p_item.url_id == r_item["url_id"]
            assert p_item.masked_url == r_item["masked_url"]
            assert p_item.estado_enlace == r_item["estado_enlace"]
            assert p_item.reglas_activadas == r_item["reglas_activadas"]


# =============================================================================
# 3. Privacidad y Enmascaramiento de Credenciales y Parámetros Sensibles
# =============================================================================

def test_regression_url_query_evidence_leak_without_at_symbol():
    """
    Prueba de regresión para verificar y prevenir la exposición de parámetros sensibles
    en la evidencia de query strings aisladas sin '@', correos ni credenciales embebidas.
    (Ej. https://ejemplo.com/ruta?token=SECRETO_FICTICIO_123&x=1)
    """
    from agents.tools.url_analysis_tools import (
        execute_tool_analizar_url,
        UrlAnalysisSessionState,
    )

    secret_value = "SECRETO_FICTICIO_123"
    raw_url = f"https://ejemplo.com/ruta?token={secret_value}&x=1"
    url_id = "URL-1"
    masked_url = sanitize_url_for_external_llm(raw_url)[0]

    # 1. Comprobación a nivel de función de sanitización con componente aislado de query
    isolated_query = f"token={secret_value}&x=1"
    sanitized_query, count = sanitize_url_for_external_llm(isolated_query)
    assert secret_value not in sanitized_query, (
        f"Fallo en sanitización de query aislada: '{sanitized_query}' conserva '{secret_value}'."
    )
    sanitized_comp, comp_count = sanitize_url_component_for_external_llm(isolated_query)
    assert secret_value not in sanitized_comp

    # 2. Comprobación de la salida de la herramienta que se entrega al modelo
    ctx = PreparationSessionContext(
        input_mode="text",
        raw_input_text=raw_url,
        validation_done=True,
        is_input_valid=True,
        links_extracted=True,
        extracted_urls=[raw_url],
        url_id_map={url_id: raw_url},
        masked_url_id_map={url_id: masked_url},
    )
    url_state = UrlAnalysisSessionState()
    tool_output = execute_tool_analizar_url(ctx, url_state, {"url_ids": [url_id]})
    tool_output_json = json.dumps(tool_output, ensure_ascii=False)
    assert secret_value not in tool_output_json, (
        f"Fallo en tool_analizar_url: el secreto '{secret_value}' se expone en la salida enviada al modelo."
    )

    # 3. Comprobación de solicitudes completas capturadas en el momento de la llamada
    capturing_client = CapturingMockLLMClient()
    tracer = AgentTracer()
    agent = AnalizadorEnlacesAgent(llm_client=capturing_client)
    result = agent.run(ctx, tracer=tracer)

    # El secreto no debe aparecer en ninguna solicitud hacia el modelo
    serialized_requests = json.dumps(capturing_client.models.calls_history, ensure_ascii=False)
    assert secret_value not in serialized_requests, (
        f"Fallo en el ciclo del agente: '{secret_value}' apareció en las solicitudes enviadas al LLM."
    )

    # 4. Conservación de la evidencia literal en el estado local del contrato
    assert result.estado == "correcto"
    assert result.cantidad_enlaces_procesados == 1
    item = result.enlaces_analizados[0]
    # En el estado local, la evidencia literal se preserva intacta para auditoría
    assert any(secret_value in s.evidencia for s in item.senales_encontradas), (
        "La evidencia literal en memoria local fue alterada indebidamente."
    )


@pytest.mark.parametrize(
    "case_id,raw_url,isolated_query,expected_secrets,expected_conserved_tokens,has_sensitive_params",
    [
        (
            "isolated_param_no_at",
            "https://ejemplo.com/ruta?token=SECRETO_FICTICIO_123&x=1",
            "token=SECRETO_FICTICIO_123&x=1",
            ["SECRETO_FICTICIO_123"],
            ["token=", "x=1"],
            True,
        ),
        (
            "multiple_sensitive_and_one_nonsensitive",
            "https://ejemplo.com/api?token=TOKEN_A&clave=CLAVE_B&user=USER_C&page=2",
            "token=TOKEN_A&clave=CLAVE_B&user=USER_C&page=2",
            ["TOKEN_A", "CLAVE_B", "USER_C"],
            ["token=", "clave=", "user=", "page=2"],
            True,
        ),
        (
            "percent_encoded_values",
            "https://ejemplo.com/auth?token=SECRETO%20ESPACIO%20123&pwd=CLAVE%21%23&sort=asc",
            "token=SECRETO%20ESPACIO%20123&pwd=CLAVE%21%23&sort=asc",
            ["SECRETO%20ESPACIO%20123", "CLAVE%21%23"],
            ["token=", "pwd=", "sort=asc"],
            True,
        ),
        (
            "embedded_credentials_and_email",
            "https://usuario_admin:clave_super_secreta_999@servidor-sospechoso.com/panel?email=victima@empresa.com&token=XYZ_TOKEN_SECRETO_123&seccion=perfil",
            "email=victima@empresa.com&token=XYZ_TOKEN_SECRETO_123&seccion=perfil",
            ["usuario_admin", "clave_super_secreta_999", "victima@empresa.com", "XYZ_TOKEN_SECRETO_123"],
            ["servidor-sospechoso.com", "seccion=perfil"],
            True,
        ),
        (
            "url_without_sensitive_params",
            "https://ejemplo.com/seguro?categoria=noticias&seccion=general&page=3",
            "categoria=noticias&seccion=general&page=3",
            [],
            ["categoria=noticias", "seccion=general", "page=3"],
            False,
        ),
    ],
)
def test_parameterized_url_query_privacy_and_local_evidence_preservation(
    case_id: str,
    raw_url: str,
    isolated_query: str,
    expected_secrets: List[str],
    expected_conserved_tokens: List[str],
    has_sensitive_params: bool,
):
    """
    Matriz de pruebas parametrizadas para validar:
    1. Parámetro sensible aislado en query sin '@'.
    2. Múltiples parámetros sensibles y al menos uno no sensible en una misma query.
    3. Valores con codificación porciento (%20, %21, etc.).
    4. Caso preexistente: URL con correo y credenciales embebidas (no regresión).
    5. URL sin parámetros sensibles (sin falsos positivos de enmascaramiento).
    6. Conservación de evidencia literal en el estado local tras el enmascaramiento externo.
    """
    from agents.tools.url_analysis_tools import (
        execute_tool_analizar_url,
        UrlAnalysisSessionState,
    )

    url_id = "URL-TEST-1"
    masked_url, url_redactions = sanitize_url_for_external_llm(raw_url)
    sanitized_query, query_redactions = sanitize_url_component_for_external_llm(isolated_query)

    # 1. Verificación de enmascaramiento a nivel de sanitizadores
    for secret in expected_secrets:
        assert secret not in masked_url, f"[{case_id}] Secreto '{secret}' expuesto en masked_url: {masked_url}"
        assert secret not in sanitized_query, f"[{case_id}] Secreto '{secret}' expuesto en sanitized_query: {sanitized_query}"

    for token in expected_conserved_tokens:
        assert token in masked_url or token in sanitized_query, (
            f"[{case_id}] Token legítimo '{token}' fue alterado indebidamente."
        )

    if not expected_secrets:
        assert url_redactions == 0
        assert query_redactions == 0
        assert masked_url == raw_url
        assert sanitized_query == isolated_query
    else:
        assert url_redactions > 0
        assert query_redactions > 0

    # 2. Verificación de salida de tool_analizar_url
    ctx = PreparationSessionContext(
        input_mode="text",
        raw_input_text=raw_url,
        validation_done=True,
        is_input_valid=True,
        links_extracted=True,
        extracted_urls=[raw_url],
        url_id_map={url_id: raw_url},
        masked_url_id_map={url_id: masked_url},
    )
    url_state = UrlAnalysisSessionState()
    tool_output = execute_tool_analizar_url(ctx, url_state, {"url_ids": [url_id]})
    tool_output_json = json.dumps(tool_output, ensure_ascii=False)

    for secret in expected_secrets:
        assert secret not in tool_output_json, (
            f"[{case_id}] Secreto '{secret}' expuesto en la salida de tool_analizar_url: {tool_output_json}"
        )

    # 3. Verificación de captura profunda en el momento de la llamada al modelo LLM
    capturing_client = CapturingMockLLMClient()
    tracer = AgentTracer()
    agent = AnalizadorEnlacesAgent(llm_client=capturing_client)
    result = agent.run(ctx, tracer=tracer)

    assert result.estado == "correcto"
    assert result.cantidad_enlaces_procesados == 1

    # Asegurar que ninguna solicitud hacia el modelo contenga los secretos
    serialized_requests = json.dumps(capturing_client.models.calls_history, ensure_ascii=False)
    for secret in expected_secrets:
        assert secret not in serialized_requests, (
            f"[{case_id}] Secreto '{secret}' expuesto en llamadas hacia el LLM: {serialized_requests}"
        )

    # 4. Conservación de evidencia literal en el estado local del contrato
    result.validate()  # Valida consistencia completa del contrato
    item = result.enlaces_analizados[0]
    if has_sensitive_params:
        # En memoria local, la evidencia literal debe mantenerse intacta
        assert any(
            any(sec in s.evidencia for sec in expected_secrets)
            for s in item.senales_encontradas
        ), f"[{case_id}] La evidencia literal en memoria local no conservó los secretos originales."



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
# 4. Caso Sin Enlaces: Especialista Aislado vs. Flujo del Orquestador
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
