# Refactorización de Lógica Compartida y Desacoplamiento Interno (Tarea 5)

Este documento registra los cambios arquitectónicos, la eliminación de duplicaciones, las pruebas de equivalencia y las limitaciones conocidas correspondientes a la **Tarea 5 del Plan de Mejoras de Detective de Estafas Digitales** (rama `refactor/logica-compartida`).

> [!IMPORTANT]
> Esta refactorización preserva estrictamente el comportamiento funcional previo: **no modifica pesos, umbrales, expresiones regulares, catálogo de TLDs, reglas de puntuación ni políticas de clasificación**.

---

## 1. Duplicaciones y Acoplamientos Eliminados

| Responsabilidad | Ubicaciones Previas | Duplicación / Acoplamiento Encontrado | Solución Implementada |
| :--- | :--- | :--- | :--- |
| **A. Derivación de reglas de URL (`REGLA-URL-01`..`05`)** | `scripts/risk_classifier.py` y `agents/tools/url_analysis_tools.py` | Inspección duplicada de subcadenas en `findings` (`"Uso engañoso"`, `"bajo costo"`, etc.), flags booleanos y regla de concurrencia `REGLA-URL-05` vs `REGLA-URL-02`. | Función canónica `classify_url_risk_signals(url_dict)` en `scripts/url_analyzer.py`, reutilizada por `RiskClassifier` y `_map_findings_to_signals_and_rules`. |
| **B. Mapeo de identificadores de enlace (`URL-1..N`)** | `agents/tools/preparation_tools.py` y `agents/analizador_enlaces/agent.py` | Construcción duplicada de `url_id_map` y `masked_url_id_map` mediante `enumerate(..., start=1)` y sanitización por enlace. | Función pura `build_session_url_maps(urls)` en `agents/common/privacy.py` y método `PreparationSessionContext.ensure_url_maps()`, manteniendo aislamiento estricto por sesión. |
| **C. Monolito de `tool_analizar_url`** | `agents/tools/url_analysis_tools.py` | `execute_tool_analizar_url` concentraba validación de IDs/ALL, análisis estático, manejo de URLs malformadas y OCR, sincronización de estado y respuesta LLM. | Descomposición en helpers de responsabilidad única: `_validate_and_resolve_url_ids`, `_analyze_single_url_item`, `_record_analyzed_item_in_session` y `_build_compact_url_tool_response`. |
| **D. Prioridades de herramientas en el ciclo LLM** | `agents/common/llm_client.py` | `run_agent_tool_loop` mantenía un diccionario acoplado (`tool_order_priority`) con nombres concretos de herramientas del Preparador, Analizador de Enlaces y Evaluador. | Se eliminó el diccionario fijo de `llm_client.py` y se agregó el parámetro opcional explícito `tool_order_priority: Optional[Dict[str, int]] = None`, inyectado desde cada agente (`PREPARADOR_TOOL_ORDER_PRIORITY` y `EVALUADOR_TOOL_ORDER_PRIORITY`). |

---

## 2. Responsabilidades por Módulo y Dependencias Explícitas

### `scripts/url_analyzer.py`
* **`classify_url_risk_signals(url_dict)`**: Recibe el diccionario producido por `analyze_single_url` (sin re-analizar cadenas ni acceder a la red) y devuelve las banderas normalizadas (`is_ip`, `has_misleading_subdomain`, `has_suspicious_tld`, `has_puny`, `has_userinfo`, `has_sensitive_params`, `has_http`), `scoring_rules` (aplicando la exclusión de `REGLA-URL-05` cuando concurre `REGLA-URL-02`), `all_rule_ids` y `is_suspicious_url`.

### `scripts/risk_classifier.py`
* **`RiskClassifier.calculate_score` y `assign_risk_level`**: Consumen directamente `classify_url_risk_signals`.
* **Compatibilidad CLI/Paquete**: Mantiene importación resiliente (`from scripts.url_analyzer import classify_url_risk_signals` con fallback `from url_analyzer import classify_url_risk_signals`) para soportar tanto la ejecución como paquete (`agents/...`, `pytest`) como la ejecución directa por CLI (`scripts/worker.py`).

### `agents/common/privacy.py` y `agents/tools/preparation_tools.py`
* **`build_session_url_maps(urls)`**: Construye de forma determinística los diccionarios `(url_id_map, masked_url_id_map)` sin estado global compartido.
* **`PreparationSessionContext.ensure_url_maps()`**: Garantiza la inicialización única y sincronizada de ambos mapas dentro de la sesión cuando existen URLs extraídas. Invocado en `execute_tool_extraer_enlaces`, `AnalizadorEnlacesAgent.run` y `execute_tool_analizar_url`.

### `agents/tools/url_analysis_tools.py`
* **`_validate_and_resolve_url_ids`**: Valida estructura y límites de `url_ids`, resuelve `"ALL"` o IDs puntuales y rechaza identificadores inexistentes o URLs sustituidas mediante `ContractValidationError`.
* **`_analyze_single_url_item`**: Ejecuta el analizador estático inyectado (`analyze_single_url` por defecto), detecta direcciones no analizables o malformadas, mapea señales y asocia advertencias OCR sin autocorregir el texto original.
* **`_record_analyzed_item_in_session`**: Registra cada `UrlItemAnalysisResult` en `UrlAnalysisSessionState` y mantiene sincronizado `prep_ctx.url_details`.
* **`_build_compact_url_tool_response`**: Construye la respuesta JSON compacta con el listado de `pending_url_ids` para el modelo.
* **`execute_tool_analizar_url`**: Orquesta el flujo público conservando exactamente su firma y contratos previos.

### `agents/common/llm_client.py` y Agentes Especialistas
* **`run_agent_tool_loop(..., tool_order_priority=None)`**: Ordena múltiples `function_calls` únicamente cuando el agente invocador declara un diccionario `tool_order_priority`.
* **`agents/preparador/agent.py`** define e inyecta `PREPARADOR_TOOL_ORDER_PRIORITY`.
* **`agents/evaluador/agent.py`** define e inyecta `EVALUADOR_TOOL_ORDER_PRIORITY`.

---

## 3. Pruebas y Verificación de Equivalencia

Se incorporó la suite `tests/test_refactor_logica_compartida.py` con 6 pruebas unitarias y de integración simulada:

1. `test_classify_url_risk_signals_equivalence_and_concurrency`: Verifica la correspondencia exacta de `REGLA-URL-01`..`05`, señales informativas y concurrencia entre `REGLA-URL-05` y `REGLA-URL-02` junto con la equivalencia en `RiskClassifier`.
2. `test_session_url_maps_stability_and_session_isolation`: Comprueba orden estable `URL-1..N`, sanitización y ausencia de contaminación entre dos instancias de `PreparationSessionContext`.
3. `test_validate_and_resolve_url_ids_edge_cases`: Valida resolución de `"ALL"`, duplicados, listas vacías, superación de `MAX_URLS_PER_CALL` e IDs desconocidos.
4. `test_tool_analizar_url_execution_and_sanitization`: Verifica la ejecución completa de `execute_tool_analizar_url`, registro en estado local, sincronización de `url_details` y sanitización en la salida hacia el LLM.
5. `test_run_agent_tool_loop_order_priority_injection`: Confirma que `run_agent_tool_loop` respeta el orden inyectado vía `tool_order_priority` cuando el modelo emite llamadas paralelas, y preserva el orden original cuando es `None`.
6. `test_full_pipeline_functional_equivalence_benchmark`: Comprueba equivalencia funcional (nivel, puntaje, reglas activadas y señales) entre el flujo determinístico (`ScamAnalyzer`) y la orquesta simulada (`OrquestadorAgent`) sobre un escenario completo con múltiples reglas de mensaje y enlace.

---

## 4. Limitaciones Conocidas Preservadas

* **Dominios con ccSLD de dos niveles (ej. `.com.ar`)**: `check_misleading_subdomains` en `scripts/url_analyzer.py` toma los últimos dos segmentos del dominio (`parts[-2:]`) como dominio base. Por diseño de esta tarea, no se modificaron las heurísticas de extracción ni las reglas de subdominios para conservar la equivalencia exacta de clasificación.
* **Prioridad implícita por ausencia**: Si un agente no pasa `tool_order_priority` a `run_agent_tool_loop`, el bucle conserva el orden en que el SDK/modelo devuelve las llamadas en el turno.
* **Alcance de la suite offline**: Las pruebas de la orquesta utilizan respuestas simuladas (`MockGeminiClient`) y excluyen `test_real_gemini_api` (`DETECTIVE_SKIP_DOTENV=1`, `GEMINI_API_KEY=""`).
