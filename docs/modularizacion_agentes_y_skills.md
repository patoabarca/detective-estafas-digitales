# Modularización de Agentes y Depuración de Skills (Tarea 6)

Este documento registra la revisión inicial, la separación de responsabilidades, la depuración de `SKILL.md`, las mediciones comparativas antes/después y las limitaciones conocidas de la **Tarea 6 del Plan de Mejoras de Detective de Estafas Digitales** (rama `refactor/modularizacion-agentes`, partida desde `main` en `c800c45`).

> [!IMPORTANT]
> Esta tarea conserva intactos los contratos públicos, ponderaciones, umbrales, patrones de detección, políticas de clasificación y el patrón de finalización anticipada del Agente Analizador de Enlaces.

---

## 1. Revisión Inicial y Frontera entre Código, Contexto LLM y Documentación

Previo a esta tarea, `AnalizadorEnlacesAgent` (`agents/analizador_enlaces/`) ya se encontraba separado en `agent.py`, `prompts.py` y `result_builder.py` con un `SKILL.md` acotado (~1.147 caracteres). En contraste, los cuatro agentes restantes mezclaban en `agent.py` múltiples capas y enviaban documentación de implementación dentro de cada turno al LLM:

| Capa / Naturaleza | Qué es en este proyecto | Qué ocurría antes de la Tarea 6 |
|---|---|---|
| **Código Python ejecutado localmente** | Coordinación del agente, validación de argumentos/contratos, enmascaramiento PII, trazabilidad, cálculo heurístico y generación de reportes/PDF. | Mezclado en `agent.py` junto con strings de prompts, esquemas JSON y construcción de respuestas `INDETERMINADO` (ej. 1.152 líneas en `orquestador/agent.py`). |
| **Contexto enviado al LLM en cada turno** | `system_instruction` (`BASE_INSTRUCTIONS` + `SKILL.md` cargados), `tool_declarations` y `contents` del historial. | Las 14 skills especialistas de Preparador, Analizador de Mensajes y Evaluador incluían rutas de módulos Python internos, nombres de métodos privados (`TextAnalyzer._detect_*`), tablas enteras de `policy.json` y textos literales de recomendaciones que el modelo no lee ni calcula. |
| **Documentación para personas** | Guías técnicas, detalles de implementación Python y catálogos completos de reglas. | Embutida en cada `SKILL.md` e inyectada repetidamente en cada llamada al modelo. |

> [!NOTE]
> Las carpetas `references/` dentro de cada skill contienen **documentación técnica de referencia para personas**. No forman parte del prompt enviado al modelo ni existe ningún mecanismo de lectura o carga bajo demanda en tiempo de ejecución; no se agregaron herramientas de lectura ni llamadas LLM adicionales.

---

## 2. Estructura Final y Responsabilidad por Módulo

### A. Agente Preparador (`agents/preparador/`)
- [`agent.py`](../agents/preparador/agent.py): Coordinador (`PreparadorAgent`), carga de 3 skills, registro de trazas y ejecución de `run_agent_tool_loop` con `PREPARADOR_TOOL_ORDER_PRIORITY`. Re-exporta constantes públicas.
- [`prompts.py`](../agents/preparador/prompts.py): `PREPARADOR_BASE_INSTRUCTIONS`, `PREPARADOR_TOOL_DECLARATIONS`, `PREPARADOR_TOOL_ORDER_PRIORITY` y `build_preparador_user_prompt(input_mode)`.
- [`result_builder.py`](../agents/preparador/result_builder.py): `build_validated_preparation_result` para consolidar los estados `fallo_herramienta`, `entrada_invalida`, `texto_no_extraible`, `con_enlaces` y `sin_enlaces`.
- **Skills depuradas + referencias:** `validar-entrada` (`references/validation_details.md`), `extraer-texto-captura` (`references/ocr_details.md`), `extraer-enlaces` (`references/url_extraction_details.md`).

### B. Agente Analizador de Mensajes (`agents/analizador_mensajes/`)
- [`agent.py`](../agents/analizador_mensajes/agent.py): Coordinador (`AnalizadorMensajesAgent`), carga de 5 skills, registro de trazas y ejecución concurrente de herramientas. Re-exporta constantes públicas.
- [`prompts.py`](../agents/analizador_mensajes/prompts.py): `ANALIZADOR_MENSAJES_BASE_INSTRUCTIONS` (eliminando doble listado redundante de herramientas), `ANALIZADOR_MENSAJES_TOOL_DECLARATIONS` (generadas de forma uniforme mediante `_make_session_text_tool_decl`) y `build_untrusted_message_prompt`.
- [`result_builder.py`](../agents/analizador_mensajes/result_builder.py): `build_validated_message_analysis_result` (diferenciando `error`, `incompleto` ante categorías omitidas y `correcto`, validando evidencia literal).
- **Skills depuradas + referencias:** `detectar-urgencia` (`references/urgency_details.md`), `detectar-amenazas` (`references/threats_details.md`), `detectar-premios` (`references/rewards_details.md`), `detectar-pedidos-datos` (`references/credentials_details.md`), `detectar-pedidos-dinero` (`references/money_requests_details.md`).

### C. Agente Evaluador (`agents/evaluador/`)
- [`agent.py`](../agents/evaluador/agent.py): Coordinador (`EvaluadorAgent`), limpieza de imports sin uso, inyección de `EVALUADOR_TOOL_ORDER_PRIORITY` y coordinación del bucle. Re-exporta constantes públicas.
- [`prompts.py`](../agents/evaluador/prompts.py): `EVALUADOR_BASE_INSTRUCTIONS`, `EVALUADOR_TOOL_ORDER_PRIORITY`, `EVALUADOR_TOOL_DECLARATIONS` (usando `_make_confirm_bool_decl`) y `build_evaluador_user_prompt`.
- [`result_builder.py`](../agents/evaluador/result_builder.py): `build_validated_evaluation_result` y `_build_incomplete_evaluation_result` (salvaguarda `INDETERMINADO` ante etapas previas fallidas o incompletas, nunca `BAJO`).
- **Skills depuradas + referencias:** `reunir-hallazgos` (`references/gather_details.md`), `calcular-puntaje` (`references/scoring_policy_reference.md`), `asignar-nivel-riesgo` (`references/risk_levels_reference.md`), `explicar-resultado` (`references/explanation_reference.md`), `recomendar-cuidados` (`references/recommendations_reference.md`), `generar-pdf` (`references/pdf_export_reference.md`).

### D. Agente Analizador de Enlaces (`agents/analizador_enlaces/`) — Referencia Conservada
- Mantiene sin cambios su estructura (`agent.py`, `prompts.py`, `result_builder.py`), finalización anticipada determinística en 1 turno y `.agents/skills/analizar-url/` (`SKILL.md` + `references/url_signals_guide.md`).

### E. Agente Orquestador (`agents/orquestador/`)
- [`agent.py`](../agents/orquestador/agent.py): Coordinador principal (`OrquestadorAgent`) del ciclo completo `AgentInputRequest -> run_agent_tool_loop -> build_final_orchestrator_response`, exponiendo `build_system_instruction()`.
- [`prompts.py`](../agents/orquestador/prompts.py): `ORQUESTADOR_SYSTEM_INSTRUCTIONS`, `ORQUESTADOR_TOOL_DECLARATIONS` y `build_orquestador_user_prompt`.
- [`delegation_tools.py`](../agents/orquestador/delegation_tools.py): `OrchestrationSessionState` (control de presupuesto de tiempo e instancias aisladas por solicitud), `execute_delegar_preparacion`, `execute_delegar_analisis_mensaje`, `execute_delegar_analisis_enlaces` (con omisión justificada `sin_enlaces`), `execute_delegar_evaluacion` y `build_orquestador_allowed_tools`.
- [`result_builder.py`](../agents/orquestador/result_builder.py): `build_omitted_url_analysis_result`, constructores de reportes seguros `INDETERMINADO` (`_make_indeterminate_report_envelope`) y ensamblador final `build_final_orchestrator_response`.
- *(Nota: El cambio en el Orquestador es estrictamente organizativo; no modifica su prompt ni reduce su tamaño de contexto.)*

---

## 3. Relación entre Agentes, Skills y Herramientas Python

1. **Orquestador (`orquestador`)** -> 4 herramientas de delegación (`delegar_preparacion`, `delegar_analisis_mensaje`, `delegar_analisis_enlaces`, `delegar_evaluacion`) definidas en `agents/orquestador/delegation_tools.py`. No carga `SKILL.md`.
2. **Preparador (`preparador`)** -> 3 skills (`validar-entrada`, `extraer-texto-captura`, `extraer-enlaces`) -> 3 herramientas en `agents/tools/preparation_tools.py`.
3. **Analizador de Mensajes (`analizador_mensajes`)** -> 5 skills (`detectar-urgencia`, `detectar-amenazas`, `detectar-premios`, `detectar-pedidos-datos`, `detectar-pedidos-dinero`) -> 5 herramientas en `agents/tools/message_analysis_tools.py`.
4. **Analizador de Enlaces (`analizador_enlaces`)** -> 1 skill (`analizar-url`) -> 1 herramienta en `agents/tools/url_analysis_tools.py`.
5. **Evaluador (`evaluador`)** -> 6 skills (`reunir-hallazgos`, `calcular-puntaje`, `asignar-nivel-riesgo`, `explicar-resultado`, `recomendar-cuidados`, `generar-pdf`) -> 6 herramientas en `agents/tools/evaluation_tools.py`.
6. **Skill de IDE (`detective-estafas-digitales`)** -> Documentación CLI/STDIN para uso directo con `scripts/worker.py` desde el chat del IDE; no es cargada por los agentes de la orquesta.

---

## 4. Comparación Antes / Después (Instrucciones de Sistema y Recorridos Simulados)

> **Aclaración metodológica:** Las mediciones siguientes corresponden a caracteres (`len(str)`) y bytes UTF-8 sobre `build_system_instruction()` y sobre los 3 escenarios determinísticos simulados (`scripts/reproduce_context_baseline.py` con `MockGeminiClient`). **No representan tokens BPE ni costos reales facturados por la API de Gemini.**

### 4.1. Tamaño de `build_system_instruction()` por Agente

| Agente | Tipo de cambio | Antes (`c800c45`) chars / bytes UTF-8 | Después chars / bytes UTF-8 | Diferencia |
|---|---|---:|---:|---:|
| `preparador` | Modularización + depuración 3 skills | 9.727 / 9.855 | 4.835 / 4.899 | -4.892 chars (-50,3%) |
| `analizador_mensajes` | Modularización + depuración 5 skills | 12.205 / 12.355 | 5.872 / 5.951 | -6.333 chars (-51,9%) |
| `analizador_enlaces` | Referencia intacta (sin cambios) | 2.071 / 2.098 | 2.071 / 2.098 | 0 (0,0%) |
| `evaluador` | Modularización + depuración 6 skills | 21.707 / 21.986 | 6.972 / 7.053 | -14.735 chars (-67,9%) |
| `orquestador` | Modularización organizativa pura | 2.490 / 2.529 | 2.490 / 2.529 | 0 (0,0%) |

### 4.2. Contexto Acumulado en los 3 Escenarios Simulados de Referencia

| Escenario | Turnos simulados (Antes -> Después) | Contexto acumulado Antes (chars / bytes UTF-8) | Contexto acumulado Después (chars / bytes UTF-8) | Reducción |
|---|:---:|---:|---:|---:|
| **ESC-01** (Texto sin enlaces) | 14 -> 14 | 219.594 / 222.168 | 118.577 / 119.827 | -101.017 chars (-46,0%) |
| **ESC-02** (Texto con 2 enlaces) | 16 -> 16 | 237.627 / 240.377 | 136.610 / 138.036 | -101.017 chars (-42,5%) |
| **ESC-03** (Captura OCR + enlace) | 17 -> 17 | 246.689 / 249.570 | 140.780 / 142.273 | -105.909 chars (-42,9%) |

Desglose en **ESC-01**:
- `orquestador`: 4 llamadas | 24.399 -> 24.399 chars (0; mejora puramente organizativa).
- `preparador`: 3 llamadas | 35.135 -> 20.459 chars (-14.676).
- `analizador_mensajes`: 2 llamadas | 31.702 -> 19.036 chars (-12.666).
- `evaluador`: 5 llamadas | 128.358 -> 54.683 chars (-73.675).

---

## 5. Actualización en Pruebas y Limitaciones Pendientes

- **Pruebas añadidas:** Se incorporó `tests/test_modularizacion_agentes.py` (13 pruebas que verifican exportaciones públicas, prompts, `result_builder`, salvaguardas `INDETERMINADO`, precondiciones de delegación, reducción de `build_system_instruction()` y conservación de turnos con reducción de contexto en ESC-01..ESC-03).
- **Ajuste documentado en `tests/test_context_measurement.py`:** El umbral histórico de la Tarea 3 `assert res["accumulated_request_chars"] > 150000` en `test_baseline_scenario_1_text_without_links` falló al reducirse ESC-01 a ~117.667 caracteres por la depuración de `SKILL.md`; se reemplazó por `assert 80000 < res["accumulated_request_chars"] < 150000` para validar tanto el contenido no trivial como el mantenimiento de la reducción lograda.
- **Limitaciones pendientes:**
  - Los escenarios simulados emplean `MockGeminiClient`; la respuesta y cantidad real de turnos ante el modelo remoto Gemini con los `SKILL.md` depurados no fue ejecutada en esta etapa (se excluyó `test_real_gemini_api`).
  - Se mantienen intactas las limitaciones funcionales ya documentadas en la Tarea 5 (heurística de ccSLD de 2 segmentos en `check_misleading_subdomains`, ausencia de lectura dinámica en runtime de `references/`).
