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
> Las mediciones a continuación corresponden a **recorridos simulados** bajo exactamente los mismos escenarios ficticios, textos de entrada y respuestas programadas definidos en la línea base de la Tarea 3 (`scripts/reproduce_context_baseline.py` y `docs/context_baseline_metrics.json`). **No representan mediciones reales de tokens cobrados, dinero facturado ni latencia de red de la API de Gemini**.

### 5.1. Comparativa de Solicitudes y Turnos por Escenario (Mismos Escenarios e Insumos)

| Escenario | Métrica | Versión Tarea 3 (Base Commit 52c17d7) | Versión Tarea 4 (Optimizada) | Diferencia Absoluta | Variación Relativa |
|---|---|:---:|:---:|:---:|:---:|
| **ESC-01**<br>*(Texto sin URLs)* | Turnos Totales<br>Turnos Enlaces<br>Chars Acumulados<br>Bytes UTF-8 | 14<br>0 *(omitido)*<br>219.594<br>222.168 | 14<br>0 *(omitido)*<br>219.594<br>222.168 | 0<br>0<br>**0**<br>**0** | 0,00%<br>0,00%<br>**0,00%**<br>**0,00%** |
| **ESC-02**<br>*(Texto 2 URLs)* | Turnos Totales<br>**Turnos Enlaces**<br>Chars Enlaces<br>Bytes UTF-8 Enlaces<br>Chars Acumulados<br>Bytes UTF-8 | 17<br>**2**<br>8.326<br>8.432<br>242.764<br>245.574 | 16<br>**1**<br>3.189<br>3.235<br>237.627<br>240.377 | -1<br>**-1**<br>**-5.137**<br>**-5.197**<br>**-5.137**<br>**-5.197** | -5,88%<br>**-50,00%**<br>**-61,70%**<br>**-61,63%**<br>**-2,11%**<br>**-2,12%** |
| **ESC-03**<br>*(Captura OCR + URL)* | Turnos Totales<br>**Turnos Enlaces**<br>Chars Enlaces<br>Bytes UTF-8 Enlaces<br>Chars Acumulados<br>Bytes UTF-8 | 18<br>**2**<br>7.837<br>7.937<br>251.404<br>254.341 | 17<br>**1**<br>3.122<br>3.166<br>246.689<br>249.570 | -1<br>**-1**<br>**-4.715**<br>**-4.771**<br>**-4.715**<br>**-4.771** | -5,56%<br>**-50,00%**<br>**-60,16%**<br>**-60,11%**<br>**-1,88%**<br>**-1,88%** |

---

### 5.2. Desglose Riguroso por Agente y Turno

Al comparar la línea base histórica contra la versión optimizada usando estrictamente los mismos datos de entrada:

#### A. Escenario 1 (ESC-01: Texto sin enlaces)
El Analizador de Enlaces se omite completamente al no existir URLs.
- **Orquestador** (4 turnos): Base = 24.399 chars (24.783 bytes) -> Opt = 24.399 chars (24.783 bytes) | **Diferencia = 0**.
- **Preparador** (3 turnos): Base = 35.135 chars (35.531 bytes) -> Opt = 35.135 chars (35.531 bytes) | **Diferencia = 0**.
- **Analizador Mensajes** (2 turnos): Base = 31.702 chars (32.062 bytes) -> Opt = 31.702 chars (32.062 bytes) | **Diferencia = 0**.
- **Evaluador** (5 turnos): Base = 128.358 chars (129.792 bytes) -> Opt = 128.358 chars (129.792 bytes) | **Diferencia = 0**.
- **Total ESC-01**: **Exact match idéntico en todos los turnos (Diferencia = 0 caracteres, 0 bytes)**.

#### B. Escenario 2 (ESC-02: Texto con dos enlaces ficticios)
- **Orquestador** (5 turnos): Base = 34.701 chars -> Opt = 34.701 chars | **Diferencia = 0**.
- **Preparador** (3 turnos): Base = 35.389 chars -> Opt = 35.389 chars | **Diferencia = 0**.
- **Analizador Mensajes** (2 turnos): Base = 32.240 chars -> Opt = 32.240 chars | **Diferencia = 0**.
- **Evaluador** (5 turnos): Base = 132.108 chars -> Opt = 132.108 chars | **Diferencia = 0**.
- **Analizador Enlaces** (2 turnos -> 1 turno):
  - **Turno 1**: Base = 3.391 chars (3.445 bytes) -> Opt = 3.189 chars (3.235 bytes) | **Diferencia: -202 chars (-210 bytes)**.
    - Causa: Retiro de la regla de instrucción redundante que ordenaba emitir un resumen textual final en `ANALIZADOR_ENLACES_BASE_INSTRUCTIONS`.
  - **Turno 2**: Base = 4.935 chars (4.987 bytes) -> Opt = **ELIMINADO por finalización anticipada**.
    - Causa: La condición `_is_url_analysis_work_complete` detecta que el lote de URLs fue procesado y corta el ciclo antes de enviar la llamada al modelo.
  - **Subtotal Analizador Enlaces**: **-5.137 caracteres (-5.197 bytes UTF-8)**.
- **Total ESC-02**: Reducción neta de **-5.137 caracteres (-5.197 bytes UTF-8)**, atribuible al **100% al Analizador de Enlaces**.

#### C. Escenario 3 (ESC-03: Captura OCR con un enlace ficticio)
- **Orquestador** (5 turnos): Base = 33.590 chars -> Opt = 33.590 chars | **Diferencia = 0**.
- **Preparador** (4 turnos): Base = 47.731 chars -> Opt = 47.731 chars | **Diferencia = 0**.
- **Analizador Mensajes** (2 turnos): Base = 31.880 chars -> Opt = 31.880 chars | **Diferencia = 0**.
- **Evaluador** (5 turnos): Base = 130.366 chars -> Opt = 130.366 chars | **Diferencia = 0**.
- **Analizador Enlaces** (2 turnos -> 1 turno):
  - **Turno 1**: Base = 3.324 chars (3.376 bytes) -> Opt = 3.122 chars (3.166 bytes) | **Diferencia: -202 chars (-210 bytes)** (poda de instrucción del sistema).
  - **Turno 2**: Base = 4.513 chars (4.561 bytes) -> Opt = **ELIMINADO por finalización anticipada**.
  - **Subtotal Analizador Enlaces**: **-4.715 caracteres (-4.771 bytes UTF-8)**.
- **Total ESC-03**: Reducción neta de **-4.715 caracteres (-4.771 bytes UTF-8)**, atribuible al **100% al Analizador de Enlaces**.

---

### 5.3. Conciliación y Explicación de Diferencias en Mediciones Exploratorias Previas

En una prueba exploratoria preliminar (registrada en el historial de la tarea), se ejecutó un script con textos sintéticos diferentes a los definidos en `scripts/reproduce_context_baseline.py`:
- En dicha prueba se utilizaron textos ad-hoc (por ejemplo, un mensaje con amenazas bancarias y pedidos urgentes de credenciales en ESC-01, y textos abreviados en ESC-02 y ESC-03).
- **Explicación comprobada de los valores observados en esa prueba exploratoria**:
  1. **ESC-01 (+809 chars)**: El texto ad-hoc incluía disparadores de amenaza y credenciales que activaron más reglas en el Evaluador (+1.014 chars acumulados en sus 5 turnos), mientras que el Preparador varió -188 chars por longitud de texto. Al re-ejecutar con el **mismo texto base** (notificación postal benigna), la diferencia es exactamente **0 caracteres**.
  2. **ESC-02 (-10.182 chars vs. -5.161 en Enlaces)** y **ESC-03 (-8.121 chars vs. -4.713 en Enlaces)**: Los textos de entrada ad-hoc eran sustancialmente más breves que los de la línea base, lo que redujo artificialmente el contexto en todos los agentes intervinientes (Orquestador, Preparador, Analizador Mensajes y Evaluador).
- **Conclusión metodológica**: Cualquier comparación entre versiones de optimización debe mantener congelados los insumos exactos. Cuando se respetan estrictamente los insumos de la línea base, no hay propagación espuria ni alteraciones colaterales fuera del Analizador de Enlaces.

---

### 5.4. Distinción Expresa de los Tres Planos de Medición

Para evitar confusiones en la interpretación técnica de los resultados:

1. **Contexto efectivamente incluido en las solicitudes al modelo (Simulación)**:
   - Es el volumen canónico (`system_instruction` + `tool_declarations` + `contents`) enviado en cada invocación de `generate_content`.
   - Se reduce en 1 turno completo (eliminación del Turno 2 en Analizador de Enlaces) y en 202 caracteres por turno en la instrucción del sistema.
2. **Respuestas de herramientas construidas localmente vs. transmitidas**:
   - `tool_analizar_url` construye en memoria un JSON estructurado (optimizado de 1.123 a 496 caracteres).
   - Debido a la **finalización anticipada**, este JSON **nunca se retransmite al modelo** en un turno subsiguiente; se consume exclusivamente en memoria local para conformar el resultado tipado `UrlAnalysisResult`.
   - Por ende, el costo de transmisión de esa respuesta hacia el modelo en el Turno 2 pasa a ser **cero**.
3. **Mediciones de simulación vs. Consumo real de la API de Gemini**:
   - Las mediciones reportadas corresponden a **caracteres y bytes UTF-8** de payloads determinísticos bajo clientes simulados.
   - **No representan consumo real de tokens BPE**, costos facturados de red ni latencias del servicio externo de Google Gemini.

---

### 5.5. Tamaño de la Respuesta de Herramienta en Casos Fijos
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

