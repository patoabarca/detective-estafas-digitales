# Optimización del Agente Analizador de Enlaces: Finalización Anticipada y Reducción de Respuestas

Este documento registra el diseño, las condiciones de control y los resultados de la **Tarea 4 del Plan de Mejoras de Detective de Estafas Digitales**: eliminación de llamadas y respuestas innecesarias en el Agente Analizador de Enlaces mediante finalización anticipada determinística y compactación de la salida de herramientas.

---

## 1. Diagnóstico y Objetivos

En las versiones previas, la interacción del Agente Analizador de Enlaces con el modelo requería invariablemente dos turnos:
1. **Turno 1**: El modelo recibía los identificadores de enlaces en `<untrusted_urls>` y emitía una invocación a `tool_analizar_url`.
2. **Turno 2**: La herramienta ejecutaba el análisis en lote sobre todos los enlaces y devolvía un JSON extenso con advertencias duplicadas. El modelo procesaba esa respuesta y emitía un resumen textual final.

Sin embargo, el resultado funcional del agente (`UrlAnalysisResult`) no utiliza el texto del modelo del Turno 2; se construye de forma 100% determinística y local a partir del estado validado en memoria (`UrlAnalysisSessionState`). En consecuencia, el Turno 2 constituía una llamada redundante cuyo resumen generado era inmediatamente descartado.

### Objetivos implementados:
- **Finalización anticipada**: Terminar el ciclo del agente inmediatamente después de procesar el lote completo de herramientas, evitando el turno de resumen descartado.
- **Reducción de respuestas**: Eliminar duplicaciones redundantes en la respuesta devuelta por `tool_analizar_url` al modelo.
- **Preservación estricta de contratos**: Conservar intactos los estados locales, la evidencia original, las validaciones de seguridad y los contratos hacia el evaluador y los reportes.

---

## 2. Condición Exacta de Finalización Anticipada

La finalización anticipada se implementó mediante un parámetro opcional en el ciclo de herramientas (`run_agent_tool_loop`), **desactivado por defecto** para todos los agentes y **activado únicamente en `AnalizadorEnlacesAgent`**:

```python
def run_agent_tool_loop(
    ...
    should_terminate_early: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
```

### Evaluación y Criterios Determinísticos

La condición es evaluada estrictamente después de ejecutar el lote de herramientas y registrar sus resultados, utilizando la función predicado `_is_url_analysis_work_complete(session_ctx, url_state)` en `agents/analizador_enlaces/agent.py`:

```python
def _is_url_analysis_work_complete(
    session_ctx: PreparationSessionContext,
    url_state: UrlAnalysisSessionState,
) -> bool:
    if "tool_analizar_url" not in url_state.tools_called:
        return False

    if url_state.tool_errors:
        return True

    expected_ids = set(session_ctx.url_id_map.keys())
    if not expected_ids:
        return True

    analyzed_ids = set(url_state.analyzed_items_by_id.keys())
    return expected_ids.issubset(analyzed_ids)
```

### Reglas de Control:
1. **Basada exclusivamente en el estado local**: Jamás se basa en una afirmación o texto emitido por el modelo.
2. **Invocación previa obligatoria**: `tool_analizar_url` debe haberse ejecutado al menos una vez.
3. **Contabilidad exhaustiva de identificadores**: Todos los identificadores esperados de la sesión (`session_ctx.url_id_map`) deben encontrarse registrados en `url_state.analyzed_items_by_id`.
4. **Soporte de lotes parciales / subconjuntos**: Si el modelo envía una lista parcial (por ejemplo `url_ids=['URL-1']` cuando existen `URL-1` y `URL-2`), `expected_ids.issubset(analyzed_ids)` devuelve `False`. Esto permite que el ciclo continúe normalmente para que el modelo procese el subconjunto restante en un turno posterior.
5. **Alineación de instrucciones**: Se retiró de `ANALIZADOR_ENLACES_BASE_INSTRUCTIONS` en `prompts.py` la orden que obligaba a emitir un resumen textual final tras la ejecución de la herramienta.

---

## 3. Tratamiento de Resultados Incompletos y Errores

Se distingue conceptualmente la **finalización del trabajo** (no restan acciones útiles que el especialista deba realizar) del **éxito del análisis** (evaluado formalmente por el contrato):

| Situación Operativa | Comportamiento del Ciclo | Estado Resultante en Contrato | Detalle de Estado | Justificación |
|---|:---:|:---:|:---:|---|
| **Lote completo analizado con éxito** | Finaliza anticipadamente (1 turno) | `correcto` | `analizados_con_senales` o `analizados_sin_senales` | Análisis completado; resumen no requerido. |
| **Dirección no analizable / malformada** | Finaliza anticipadamente (1 turno) | `incompleto` | `direccion_no_analizable` | La URL no posee estructura válida; reintentar no aporta información. **No se convierte a 'correcto' ni a 'riesgo bajo'**. |
| **Fallo técnico en herramienta** | Finaliza anticipadamente (1 turno) | `error` | `fallo_herramienta` | Error irrecuperable en la herramienta; se propaga el estado de error. |
| **Lote parcial / subconjunto** | Continúa el ciclo | Depende del turno siguiente | Si el modelo no procesa el resto, `incompleto` (`enlaces_omitidos`) | Se da la oportunidad de completar los enlaces pendientes. |
| **Modelo termina sin llamar a herramienta** | Termina por falta de `function_calls` | `incompleto` | `enlaces_omitidos` | Enlaces requeridos no procesados. |

---

## 4. Reducción de la Respuesta Destinada al Modelo

### 4.1. Duplicaciones Eliminadas

Se optimizó la estructura devuelta por `tool_analizar_url` en `agents/tools/url_analysis_tools.py`:
- **Array global de advertencias (`warnings`)**: Se eliminó del JSON enviado al modelo. En la versión previa, repetía textualmente las mismas advertencias que ya figuraban dentro de cada ítem analizado.
- **Campo `descripcion` en señales**: Se retiró de cada señal enviada al modelo. El par (`id_regla`, `tipo_senal`) junto a la `evidencia` sanitizada proporciona toda la semántica requerida sin duplicar cadenas descriptivas largas.
- **Array `advertencias` por ítem**: Se sustituyó por `advertencias_especificas`, presente únicamente ante anomalías no estructuradas como reglas (ej. formato inválido o distorsión OCR).
- **Incorporación de `pending_url_ids`**: Se añadió una lista explícita con los identificadores que restan procesar en la sesión (útil para que el modelo decida la continuación en lotes parciales).

### 4.2. Preservación Local y Privacidad
- **Estado local íntegro**: El objeto `url_state` en memoria conserva todas las advertencias completas, textos de hallazgos originales y evidencias sin abreviar. La función `build_validated_url_analysis_result` utiliza `url_state` para construir el contrato completo para el Evaluador.
- **Privacidad sin fisuras**: Se mantuvieron todas las llamadas a `sanitize_url_component_for_external_llm` y `sanitize_text_for_external_llm`, garantizando que tokens, contraseñas o PII en URLs no se expongan hacia el modelo.

### 4.3. Separación de Medición: Construcción vs. Transmisión
Se distingue entre:
1. **Tamaño de la respuesta construida**: Medición estática del JSON devuelto por la función de herramienta.
2. **Contexto efectivamente transmitido al modelo**: Cuando la finalización anticipada actúa, **la respuesta de la herramienta no se envía de vuelta al modelo** en un turno posterior, evitando transmitir esos caracteres por completo.

---

## 5. Comparativa Reproducible Antes / Después (Línea Base Simulada)

> **Nota metodológica obligatoria**:  
> Las mediciones a continuación corresponden a **recorridos simulados** bajo exactamente los mismos escenarios ficticios y respuestas programadas que en la Tarea 3. **No representan mediciones reales de tokens cobrados, dinero facturado ni latencia de red de la API de Gemini**.

### 5.1. Comparativa de Solicitudes y Turnos por Escenario

| Escenario | Métrica | Versión Tarea 3 (Base Commit 52c17d7) | Versión Tarea 4 (Optimizada) | Diferencia Absoluta | Variación Relativa |
|---|---|:---:|:---:|:---:|:---:|
| **ESC-01**<br>*(Texto sin URLs)* | Turnos Totales<br>Turnos Enlaces<br>Chars Acumulados<br>Bytes UTF-8 | 14<br>0 *(omitido)*<br>219.594<br>222.168 | 14<br>0 *(omitido)*<br>220.403<br>223.000 | 0<br>0<br>+809<br>+832 | 0,0%<br>0,0%<br>+0,37%<br>+0,37% |
| **ESC-02**<br>*(Texto 2 URLs)* | Turnos Totales<br>**Turnos Enlaces**<br>Chars Enlaces<br>Chars Acumulados<br>Bytes UTF-8 | 17<br>**2**<br>8.326<br>242.764<br>245.574 | 16<br>**1**<br>3.165<br>232.582<br>235.299 | -1<br>**-1**<br>**-5.161**<br>-10.182<br>-10.275 | -5,9%<br>**-50,0%**<br>**-62,0%**<br>-4,19%<br>-4,18% |
| **ESC-03**<br>*(Captura OCR + URL)* | Turnos Totales<br>**Turnos Enlaces**<br>Chars Enlaces<br>Chars Acumulados<br>Bytes UTF-8 | 18<br>**2**<br>7.837<br>251.404<br>254.341 | 17<br>**1**<br>3.124<br>243.283<br>246.117 | -1<br>**-1**<br>**-4.713**<br>-8.121<br>-8.224 | -5,6%<br>**-50,0%**<br>**-60,1%**<br>-3,23%<br>-3,23% |

### 5.2. Tamaño de la Respuesta de Herramienta en Casos Fijos
Medición escalar de la salida JSON de `tool_analizar_url` ante caso sintético de IP directa (`http://192.168.1.50/login`):

| Métrica | Antes (Tarea 3) | Después (Tarea 4) | Reducción | % Reducción |
|---|:---:|:---:|:---:|:---:|
| **Caracteres JSON** | 1.123 | **496** | -627 | **-55,8%** |
| **Bytes UTF-8** | 1.132 | **496** | -636 | **-56,2%** |

---

## 6. Diagnóstico del Antecedente de Fallo Intermitente en Timeout

Durante la validación de la Tarea 3 se registró un fallo intermitente en:
`test_orchestrator_aborts_and_reports_error_when_global_time_budget_exhausted`.

### Causa Identificada:
1. El test utilizaba `max_total_elapsed_seconds=0.0001` y ejecutaba `time.sleep(0.001)` antes de llamar a `orq.run()`.
2. Sin embargo, el temporizador inicial del orquestador (`t0 = time.monotonic()`) se inicializa **dentro de `orq.run()`**, por lo que el `sleep` previo no consumía el presupuesto asignado.
3. El tiempo de ejecución entre `t0` y la verificación de presupuesto fluctuaba entre 70 y 110 microsegundos según la carga del procesador:
   - Si tardaba > 100 µs, se agotaba en el orquestador (`"Se superó el presupuesto total de tiempo..."`).
   - Si tardaba < 100 µs, alcanzaba a delegar en el preparador, cuyo ciclo interno excedía los microsegundos restantes y lanzaba `"Tiempo máximo de ejecución excedido..."`, formateado luego como `"tiempo límite excedido"`.
   - La aserción original buscaba textualmente `"tiempo máximo"` en lugar de la cadena adaptada para usuario `"tiempo límite excedido"`.

### Corrección Determinística:
Se aplicó un reloj simulado controlado con `monkeypatch.setattr(time, "monotonic", fake_monotonic)`, eliminando dependencias de microsegundos del planificador y garantizando un comportamiento 100% determinístico sin ampliar tiempos artificialmente.
