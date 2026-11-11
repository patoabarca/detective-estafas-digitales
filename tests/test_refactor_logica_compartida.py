"""
Pruebas de Validación del Refactor de Lógica Compartida (Tarea 5).

Verifica:
1. Equivalencia funcional de la derivación centralizada de reglas de URL (`classify_url_risk_signals`).
2. Mapeo estable de identificadores de enlaces (`build_session_url_maps`, `ensure_url_maps`) y aislamiento estricto de sesiones.
3. Manejo de identificadores desconocidos, subconjuntos, solicitudes repetidas y "ALL" en `tool_analizar_url`.
4. Sanitización rigurosa de evidencias y respuestas destinadas al modelo externo.
5. Inyección explícita de prioridades de ordenamiento de herramientas en `run_agent_tool_loop` sin acoplamiento interno.
6. Equivalencia integral de evaluación en modo determinístico y orquestado.
"""

from __future__ import annotations

from typing import Any, Dict, List
import pytest

from scripts.url_analyzer import analyze_single_url, classify_url_risk_signals
from scripts.risk_classifier import RiskClassifier
from scripts.worker import load_policy
from agents.common.privacy import build_session_url_maps, sanitize_url_for_external_llm
from agents.common.contracts import (
    AgentInputRequest,
    ContractValidationError,
)
from agents.common.llm_client import run_agent_tool_loop
from agents.common.traceability import AgentTracer
from agents.tools.preparation_tools import PreparationSessionContext
from agents.tools.url_analysis_tools import (
    UrlAnalysisSessionState,
    _validate_and_resolve_url_ids,
    execute_tool_analizar_url,
)
from agents.preparador.agent import PREPARADOR_TOOL_ORDER_PRIORITY
from agents.evaluador.agent import EVALUADOR_TOOL_ORDER_PRIORITY
from web.analysis_adapter import analyze_text


# ---------------------------------------------------------------------------
# 1. Derivación centralizada de reglas de URL
# ---------------------------------------------------------------------------

def test_classify_url_risk_signals_equivalence_and_concurrency():
    """
    Verifica que classify_url_risk_signals clasifique fielmente cada regla y
    respete la regla de concurrencia: REGLA-URL-05 no suma para puntaje si REGLA-URL-02 está presente.
    """
    # Caso 1: IP directa -> REGLA-URL-01
    u_ip = analyze_single_url("http://192.168.1.50/login")
    sig_ip = classify_url_risk_signals(u_ip)
    assert sig_ip["is_ip"] is True
    assert sig_ip["scoring_rules"] == ["REGLA-URL-01"]
    assert sig_ip["is_suspicious_url"] is True

    # Caso 2: Subdominio engañoso y TLD sospechoso -> Concurrencia REGLA-URL-02 y REGLA-URL-05
    # En scoring_rules solo debe ir REGLA-URL-02 para evitar doble cómputo, pero ambas en all_rule_ids
    u_combo = analyze_single_url("http://bbva.seguridad.xyz/login")
    sig_combo = classify_url_risk_signals(u_combo)
    assert sig_combo["has_misleading_subdomain"] is True
    assert sig_combo["has_suspicious_tld"] is True
    assert sig_combo["scoring_rules"] == ["REGLA-URL-02"]
    assert "REGLA-URL-02" in sig_combo["all_rule_ids"]
    assert "REGLA-URL-05" in sig_combo["all_rule_ids"]
    assert sig_combo["is_suspicious_url"] is True

    # Caso 3: Solo TLD sospechoso sin subdominio engañoso -> REGLA-URL-05 suma
    u_tld = analyze_single_url("http://promocion-especial.xyz/regalo")
    sig_tld = classify_url_risk_signals(u_tld)
    assert sig_tld["has_misleading_subdomain"] is False
    assert sig_tld["has_suspicious_tld"] is True
    assert sig_tld["scoring_rules"] == ["REGLA-URL-05"]

    # Caso 4: Punycode -> REGLA-URL-03
    u_puny = analyze_single_url("https://xn--bncogalicia-77a.com/portal")
    sig_puny = classify_url_risk_signals(u_puny)
    assert sig_puny["has_puny"] is True
    assert "REGLA-URL-03" in sig_puny["scoring_rules"]

    # Caso 5: Credenciales embebidas -> REGLA-URL-04
    u_creds = analyze_single_url("https://admin:secreto123@portal.com/home")
    sig_creds = classify_url_risk_signals(u_creds)
    assert sig_creds["has_userinfo"] is True
    assert "REGLA-URL-04" in sig_creds["scoring_rules"]

    # Caso 6: URL legítima sin señales de riesgo
    u_legit = analyze_single_url("https://www.mercadolibre.com/ayuda")
    sig_legit = classify_url_risk_signals(u_legit)
    assert sig_legit["is_suspicious_url"] is False
    assert len(sig_legit["scoring_rules"]) == 0


# ---------------------------------------------------------------------------
# 2. Mapeo estable de identificadores y aislamiento de sesiones
# ---------------------------------------------------------------------------

def test_session_url_maps_stability_and_session_isolation():
    """
    Verifica que build_session_url_maps y ensure_url_maps generen identificadores estables
    y no compartan estado mutable entre sesiones concurrentes o independientes.
    """
    urls_a = ["https://sitio-a.com/login?token=abc", "http://sitio-b.xyz"]
    urls_b = ["http://sitio-c.com", "https://sitio-d.org"]

    id_map_a, masked_map_a = build_session_url_maps(urls_a)
    id_map_b, masked_map_b = build_session_url_maps(urls_b)

    # Estabilidad en orden e IDs
    assert list(id_map_a.keys()) == ["URL-1", "URL-2"]
    assert list(id_map_b.keys()) == ["URL-1", "URL-2"]
    assert id_map_a["URL-1"] == urls_a[0]
    assert id_map_b["URL-1"] == urls_b[0]

    # Enmascaramiento correcto
    assert "[VALOR_URL_OCULTO]" in masked_map_a["URL-1"]
    assert "token=abc" not in masked_map_a["URL-1"]

    # Aislamiento en contextos de preparación
    ctx_1 = PreparationSessionContext(input_mode="text", extracted_urls=urls_a)
    ctx_2 = PreparationSessionContext(input_mode="text", extracted_urls=urls_b)

    ctx_1.ensure_url_maps()
    ctx_2.ensure_url_maps()

    assert ctx_1.url_id_map["URL-1"] == urls_a[0]
    assert ctx_2.url_id_map["URL-1"] == urls_b[0]
    # Modificar ctx_1 no afecta ctx_2
    ctx_1.url_id_map["URL-1"] = "modificado"
    assert ctx_2.url_id_map["URL-1"] == urls_b[0]


# ---------------------------------------------------------------------------
# 3. Validación y responsabilidades modulares en tool_analizar_url
# ---------------------------------------------------------------------------

def test_validate_and_resolve_url_ids_edge_cases():
    """
    Verifica el comportamiento de _validate_and_resolve_url_ids ante:
    - 'ALL'
    - Subconjuntos válidos
    - Identificadores repetidos
    - IDs desconocidos o URLs inventadas/sustituidas (rechazo estricto)
    - Parámetros inválidos
    """
    ctx = PreparationSessionContext(
        input_mode="text",
        extracted_urls=["https://banco.com/1", "https://banco.com/2", "https://banco.com/3"]
    )
    ctx.ensure_url_maps()

    # Caso 1: ALL expande en orden
    res_all = _validate_and_resolve_url_ids(["ALL"], ctx)
    assert res_all == ["URL-1", "URL-2", "URL-3"]

    # Caso 2: Subconjunto
    res_sub = _validate_and_resolve_url_ids(["URL-2"], ctx)
    assert res_sub == ["URL-2"]

    # Caso 3: Repetidos se deduplican conservando orden
    res_rep = _validate_and_resolve_url_ids(["URL-3", "URL-1", "URL-3"], ctx)
    assert res_rep == ["URL-3", "URL-1"]

    # Caso 4: ID desconocido o sustitución de URL rechazada
    with pytest.raises(ContractValidationError) as exc_unknown:
        _validate_and_resolve_url_ids(["URL-99"], ctx)
    assert "inválido, inexistente o URL sustituida" in str(exc_unknown.value)

    # Caso 5: URL inventada en lugar del ID
    with pytest.raises(ContractValidationError) as exc_invented:
        _validate_and_resolve_url_ids(["https://sitio-malicioso.com"], ctx)
    assert "inválido, inexistente o URL sustituida" in str(exc_invented.value)

    # Caso 6: Lista vacía o tipos incorrectos
    with pytest.raises(ContractValidationError):
        _validate_and_resolve_url_ids([], ctx)
    with pytest.raises(ContractValidationError):
        _validate_and_resolve_url_ids([""], ctx)
    with pytest.raises(ContractValidationError):
        _validate_and_resolve_url_ids([123], ctx)


def test_tool_analizar_url_execution_and_sanitization():
    """
    Verifica que execute_tool_analizar_url opere de forma modular,
    reutilice análisis existentes sin duplicar ejecuciones y sanitice los resultados.
    """
    ctx = PreparationSessionContext(
        input_mode="text",
        extracted_urls=["https://admin:pass123@bancogalicia.seguridad.xyz/login?token=sensitive"]
    )
    url_state = UrlAnalysisSessionState()

    # Primera llamada
    res1 = execute_tool_analizar_url(ctx, url_state, {"url_ids": ["URL-1"]})
    assert res1["status"] == "ok"
    assert res1["processed_count"] == 1
    assert res1["pending_url_ids"] == []

    # Verificar que el resultado retornado al modelo esté sanitizado
    result_item = res1["results"][0]
    assert "[CREDENCIAL_URL_OCULTA]" in result_item["masked_url"]
    assert "[VALOR_URL_OCULTO]" in result_item["masked_url"]
    assert "pass123" not in str(result_item)
    assert "sensitive" not in str(result_item)

    # Segunda llamada para el mismo ID (reutilización idempotente sin re-análisis)
    call_count = len(url_state.analyzed_items_by_id)
    res2 = execute_tool_analizar_url(ctx, url_state, {"url_ids": ["URL-1"]})
    assert res2["status"] == "ok"
    assert len(url_state.analyzed_items_by_id) == call_count


# ---------------------------------------------------------------------------
# 4. Ordenamiento desacoplado en run_agent_tool_loop
# ---------------------------------------------------------------------------

class DummyCall:
    def __init__(self, name: str, args: Dict[str, Any]):
        self.name = name
        self.args = args


class DummyModelResponse:
    def __init__(self, function_calls: List[DummyCall]):
        self.function_calls = function_calls
        self.text = "OK"
        self.usage_metadata = None


class DummyMockClient:
    is_mock_client = True

    def __init__(self, responses: List[DummyModelResponse]):
        self.responses = list(responses)
        self.models = self

    def generate_content(self, *args, **kwargs):
        if self.responses:
            return self.responses.pop(0)
        return DummyModelResponse([])


def test_run_agent_tool_loop_order_priority_injection():
    """
    Demuestra que run_agent_tool_loop no contiene prioridades cableadas internamente
    y respeta el orden explícito provisto por tool_order_priority.
    """
    tracer = AgentTracer()
    executed_tools: List[str] = []

    def make_tool(name: str):
        def tool_fn(args):
            executed_tools.append(name)
            return {"status": "ok"}
        return tool_fn

    allowed = {
        "tool_c": make_tool("tool_c"),
        "tool_b": make_tool("tool_b"),
        "tool_a": make_tool("tool_a"),
    }
    decls = [{"name": k, "description": k} for k in allowed.keys()]

    # El modelo devuelve las llamadas en orden inverso [c, b, a]
    calls = [DummyCall("tool_c", {}), DummyCall("tool_b", {}), DummyCall("tool_a", {})]
    client = DummyMockClient([DummyModelResponse(calls), DummyModelResponse([])])

    # 1. Sin tool_order_priority: se ejecutan en el orden devuelto por el modelo
    run_agent_tool_loop(
        agent_name="test_agent",
        system_instruction="test",
        user_prompt="test",
        allowed_tools=allowed,
        tool_declarations=decls,
        tracer=tracer,
        llm_client=client,
        tool_order_priority=None,
    )
    assert executed_tools == ["tool_c", "tool_b", "tool_a"]

    # 2. Con tool_order_priority inyectado: se reordenan según la prioridad provista
    executed_tools.clear()
    custom_priority = {"tool_a": 10, "tool_b": 20, "tool_c": 30}
    client2 = DummyMockClient([DummyModelResponse(calls), DummyModelResponse([])])

    run_agent_tool_loop(
        agent_name="test_agent",
        system_instruction="test",
        user_prompt="test",
        allowed_tools=allowed,
        tool_declarations=decls,
        tracer=tracer,
        llm_client=client2,
        tool_order_priority=custom_priority,
    )
    assert executed_tools == ["tool_a", "tool_b", "tool_c"]


# ---------------------------------------------------------------------------
# 5. Equivalencia integral de evaluación
# ---------------------------------------------------------------------------

def test_full_pipeline_functional_equivalence_benchmark():
    """
    Comprueba que el refactor mantenga exactamente los mismos niveles de riesgo,
    puntajes y reglas activadas para los casos representativos del sistema.
    """
    policy = load_policy()
    classifier = RiskClassifier(policy)

    # Caso Phishing bancario con amenaza y subdominio engañoso
    text_phishing = (
        "Su cuenta será suspendida de forma urgente en las próximas horas. "
        "Ingrese a https://mercadopago.verificacion-cuenta.com/login"
    )
    rep_phishing = analyze_text(text_phishing, input_mode="text")
    assert rep_phishing["risk_assessment"]["level"] == "ALTO"
    assert rep_phishing["risk_assessment"]["score"] >= 50
    act_rules = rep_phishing["risk_assessment"]["activated_rules"]
    assert any("REGLA-ING-01" in r for r in act_rules)
    assert any("REGLA-URL-02" in r for r in act_rules)

    # Caso Legítimo
    text_legit = "Hola Juan, te comparto el resumen de la reunión de trabajo de hoy. Saludos cordiales."
    rep_legit = analyze_text(text_legit, input_mode="text")
    assert rep_legit["risk_assessment"]["level"] == "BAJO"
    assert rep_legit["risk_assessment"]["score"] == 0

    # Caso de urgencia aislada
    text_urgency = "Por favor confirmar asistencia en las proximas horas para la reserva."
    rep_urg = analyze_text(text_urgency, input_mode="text")
    assert rep_urg["risk_assessment"]["level"] == "BAJO"
    assert rep_urg["risk_assessment"]["score"] == 15
    assert "apuro o urgencia temporal" in rep_urg["non_technical_explanation"]
