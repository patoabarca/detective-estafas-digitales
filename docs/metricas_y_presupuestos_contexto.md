# Métricas de Consumo de Tokens y Presupuestos de Contexto

Este documento consolida el análisis, las mejoras técnicas implementadas y las líneas base reproducibles correspondientes a la **Tarea 3 del Plan de Mejoras de Detective de Estafas Digitales**: medición confiable del consumo de tokens, distinción entre datos ausentes y ceros reales, trazabilidad de componentes opcionales y establecimiento de presupuestos de contexto cuantitativos sin dependencia de llamadas a la red.

---

## 1. Diagnóstico del Registro de Tokens y Correcciones Implementadas

### 1.1. Causas Técnicas de los Problemas Previos

En la versión previa del sistema se detectaron inconsistencias en la captura y visualización de métricas de tokens reportadas por el SDK de Gemini (`google-genai`):

1. **Coerción de datos ausentes en ceros absolutos**:  
   En `agents/common/llm_client.py`, la extracción de campos utilizaba expresiones como:
   ```python
   prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
   output_tokens = getattr(usage, "candidates_token_count", 0) or 0
   total_tokens = getattr(usage, "total_token_count", 0) or 0
   ```
   Esta lógica convertía valores ausentes (`None` o campos omitidos por el proveedor) en enteros `0`, desvirtuando la realidad del consumo e impidiendo distinguir entre una llamada que no consumió tokens y una llamada donde el proveedor no reportó la métrica.
2. **Suma ciega de componentes en la agregación**:  
   El trazador (`AgentTracer`) acumulaba valores numéricos asumiendo que los componentes parciales sumaban siempre el total. Cuando los componentes eran `0` forzados y el total era mayor a cero, las sumas quedaban inconsistentes.
3. **Omisión de componentes avanzados de Gemini 2.5 / 3.5**:  
   No se capturaban tokens en caché (`cached_content_token_count`), tokens de razonamiento (`thoughts_token_count`) ni tokens de prompt para invocación de herramientas (`tool_use_prompt_token_count`).
4. **Agregación y riesgo de doble cómputo**:  
   Al consultar el consumo total de la orquesta, si no se particionaban estrictamente los registros por agente, existía el riesgo de duplicar tokens en llamadas donde el orquestador delegaba o registraba eventos sobre el mismo paso.
5. **Tratamiento de llamadas fallidas y reintentos**:  
   Una llamada fallida por timeout o excepción de red no debía atribuirse 0 tokens como si hubiera sido gratuita, sino registrarse como fallo con consumo no disponible. Asimismo, los reintentos automáticos por backoff deben discriminarse de las llamadas lógicas.

---

### 1.2. Análisis del Caso Histórico Previo (`prompt=0, output=0, total=3022`)

En una ejecución previa de pruebas reales con Gemini, el trazador registró un reporte desconcertante:
`prompt=0, output=0, total=3022`.

#### Causa en el código local
El objeto `usage_metadata` provisto por el SDK contenía `total_token_count = 3022`, pero los atributos `prompt_token_count` y `candidates_token_count` vinieron nulos (`None`) o no fueron poblados en la respuesta del modelo. La función local forzó esos campos ausentes a `0`, creando la falsa impresión de que se consumieron cero tokens de entrada y salida pero 3.022 en total.

#### Causa original en el proveedor (Gemini API)
La causa exacta por la cual la API de Gemini omitió los componentes de entrada y salida en esa solicitud específica queda **técnicamente indeterminada**.  
Al no haberse conservado en dicha sesión histórica los registros crudos de tráfico de red a nivel de socket (raw HTTP wire logs) ni las cabeceras de respuesta del endpoint de Gemini, no es posible discernir si se debió a un comportamiento de streaming parcial, a una respuesta generada en una versión preliminar de la API, o a una asimetría transitoria en la agregación interna de métricas del clúster de Google.

---

### 1.3. Nuevo Esquema de Registro y Estados de Cobertura

Para resolver de raíz estas ambigüedades, se implementó la estructura `LLMCallRecord` en `agents/common/traceability.py` y se refactorizó `agents/common/llm_client.py`:

```python
@dataclass
class LLMCallRecord:
    agent: str
    model: str
    prompt_tokens: Optional[int]
    output_tokens: Optional[int]
    total_tokens: Optional[int]
    cached_tokens: Optional[int] = None
    thoughts_tokens: Optional[int] = None
    tool_use_prompt_tokens: Optional[int] = None
    is_retry: bool = False
    success: bool = True
    error_message: Optional[str] = None
```

#### Estados de Cobertura Documentados
El sistema evalúa la cobertura de métricas por agente y a nivel global bajo tres estados canónicos:

| Estado de Cobertura | Condición | Representación en UI / Trazas |
|---|---|---|
| `complete` | El total y los dos componentes principales (`prompt` y `output`) están reportados como enteros por el proveedor. | Muestra las cifras exactas desglosadas (ej. `prompt: 120, output: 45, total: 165`). |
| `partial` | Se dispone del total reportado pero falta al menos un componente principal (o viceversa). | Muestra el total conocido agregando la leyenda `(parcial)` (ej. `3022 (parcial)`). |
| `unavailable` | No se dispone de ningún dato de consumo confirmado (llamada fallida, omitida o sin metadatos de uso). | Muestra explícitamente `no disponible`. Nunca `0`. |

#### Reglas de Agregación
- **Preservación del total del proveedor**: Si el proveedor informa `total_tokens = 3022` y los componentes faltan, el total reportado es `3022`, no se recalcula ni se descarta.
- **Particionamiento por agente**: Cada registro pertenece a un único agente emisor. El total de la sesión es la suma particionada de las llamadas exitosas registradas por cada especialista y el orquestador.
- **Fallas y reintentos**: Las llamadas marcadas con `success=False` no aportan tokens y registran su cobertura como `unavailable`. Los reintentos se marcan con `is_retry=True` para su análisis independiente.

---

## 2. Línea Base Reproducible del Contexto Enviado

### 2.1. Metodología de Medición

Para medir el contexto real sin realizar llamadas a la API de Gemini ni depender de conexión a internet, se desarrolló el módulo `agents/common/context_metrics.py` y el script de prueba `scripts/reproduce_context_baseline.py`.

#### Criterios Fundamentales de Medición:
1. **Serialización Canónica Determinística**:  
   Se utiliza JSON canónico estándar (`json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'))`). Esto garantiza que los tamaños sean idénticos en cualquier entorno y sistema operativo.
2. **Unidades de Medida**:  
   Se mide estrictamente en:
   - **Caracteres Unicode**: Longitud escalar de la cadena canónica (`len(text)`).
   - **Bytes UTF-8**: Tamaño en bytes de la cadena codificada en UTF-8 (`len(text.encode('utf-8'))`).
3. **No Equivalencia**:  
   **Estas medidas NO representan conteos de tokens ni bytes de tráfico de red (HTTP wire bytes)**. El conteo de tokens depende del tokenizador BPE del modelo y el tráfico HTTP incluye cabeceras, compresión gzip/brotli y encapsulamiento TLS.
4. **Desglose de Componentes sin Doble Conteo**:  
   En cada turno de interacción con el modelo se miden:
   - `system_instruction`: Texto de la instrucción de sistema del agente.
   - `tool_declarations`: Declaraciones JSON de herramientas expuestas al modelo.
   - `contents`: Historial acumulado de contenidos enviado en el turno.
   - `tool_responses_breakdown`: Desglose informativo de las respuestas de herramientas dentro de `contents`. **No se suman adicionalmente al total del turno** para evitar duplicación, ya que se encuentran embebidas en los `contents`.

---

### 2.2. Resultados Comparativos de la Línea Base (3 Escenarios)

La línea base fue ejecutada de manera 100% determinística y offline con los tres escenarios estándar requeridos, generando el archivo `docs/context_baseline_metrics.json`:

1. **ESC-01 (Texto sin enlaces)**: "URGENTE: Su cuenta bancaria ha sido bloqueada. Ingrese sus credenciales para rehabilitarla inmediatamente o perderá su saldo."
2. **ESC-02 (Texto con dos enlaces ficticios)**: "Promoción imperdible en https://promo-banco.xyz/login y verifique en http://192.168.1.50/promo"
3. **ESC-03 (Captura con OCR simulado y enlace)**: Simulación de captura con OCR legible que extrae texto fraudulento y el enlace `https://banco-seguro-actualizacion.com/login`.

#### Tabla General de Consumo de Contexto Acumulado

| Escenario | Modo de Entrada | Agentes Intervinientes | Turnos Totales | Contexto Acumulado (Caracteres) | Contexto Acumulado (Bytes UTF-8) |
|---|---|:---:|:---:|:---:|:---:|
| **ESC-01** | Texto directo | 4 agentes | 14 | **219.594** | **222.168** |
| **ESC-02** | Texto directo | 5 agentes | 17 | **242.764** | **245.574** |
| **ESC-03** | Captura OCR | 5 agentes | 18 | **251.404** | **254.341** |

---

### 2.3. Desglose Detallado por Agente y Turnos

#### ESC-01: Texto sin Enlaces (14 turnos simulados)
*El Analizador de Enlaces es omitido por el Orquestador al no detectarse URLs.*

| Agente | Turnos | Caracteres Acumulados | Bytes UTF-8 Acumulados | % Contexto del Flujo |
|---|:---:|:---:|:---:|:---:|
| **orquestador** | 4 | 24.399 | 24.669 | 11,1% |
| **preparador** | 3 | 35.135 | 35.549 | 16,0% |
| **analizador_mensajes** | 2 | 31.702 | 32.062 | 14,4% |
| **analizador_enlaces** | 0 | 0 | 0 | 0,0% *(omitido)* |
| **evaluador** | 5 | 128.358 | 129.888 | 58,5% |
| **Total Escenario** | **14** | **219.594** | **222.168** | **100,0%** |

#### ESC-02: Texto con Dos Enlaces Ficticios (17 turnos simulados)
*Participan los 5 agentes de la orquesta completa.*

| Agente | Turnos | Caracteres Acumulados | Bytes UTF-8 Acumulados | % Contexto del Flujo |
|---|:---:|:---:|:---:|:---:|
| **orquestador** | 5 | 34.701 | 35.061 | 14,3% |
| **preparador** | 3 | 35.389 | 35.805 | 14,6% |
| **analizador_mensajes** | 2 | 32.240 | 32.605 | 13,3% |
| **analizador_enlaces** | 2 | 8.326 | 8.423 | 3,4% |
| **evaluador** | 5 | 132.108 | 133.680 | 54,4% |
| **Total Escenario** | **17** | **242.764** | **245.574** | **100,0%** |

#### ESC-03: Captura de Pantalla con OCR Simulado y Enlace (18 turnos simulados)
*Se activa el procesamiento OCR en el preparador y el análisis de enlace posterior.*

| Agente | Turnos | Caracteres Acumulados | Bytes UTF-8 Acumulados | % Contexto del Flujo |
|---|:---:|:---:|:---:|:---:|
| **orquestador** | 5 | 33.590 | 33.950 | 13,4% |
| **preparador** | 4 | 47.731 | 48.294 | 19,0% |
| **analizador_mensajes** | 2 | 31.880 | 32.244 | 12,7% |
| **analizador_enlaces** | 2 | 7.837 | 7.930 | 3,1% |
| **evaluador** | 5 | 130.366 | 131.923 | 51,8% |
| **Total Escenario** | **18** | **251.404** | **254.341** | **100,0%** |

#### Observaciones Técnicas Clave:
1. **Predominancia del Agente Evaluador**: El Evaluador representa entre el 51% y el 58% de todo el contexto acumulado de la orquesta debido a que sus instrucciones incorporan el catálogo completo de reglas de severidad, umbrales y salvaguardas, además de recibir el estado agregado de todos los agentes previos a lo largo de 5 turnos de refinamiento heurístico.
2. **Eficiencia del Analizador de Enlaces**: El especialista modularizado tiene una huella de contexto reducida (~7.800 a 8.300 caracteres acumulados en 2 turnos), representando apenas ~3,1% a 3,4% del contexto total en flujos con enlaces, y 0% cuando no hay URLs.
3. **Impacto del OCR en el Preparador**: En ESC-03, el contexto del Preparador aumenta de ~35k a ~47,7k caracteres debido al turno adicional de invocación de herramienta local OCR y la validación del texto extraído.

---

## 3. Presupuestos de Contexto para el Analizador de Enlaces

### 3.1. Justificación del Cambio de Aserciones Fijas a Presupuestos

En pruebas unitarias previas se comprobaban igualdades exactas (`assert pilot_chars == 2273`). Este enfoque resultaba excesivamente frágil: cualquier ajuste menor de puntuación, redacción de docstrings o saltos de línea quebraba los tests a pesar de que el código cumplía holgadamente su objetivo de reducción.

Se reemplazaron dichas aserciones rígidas por **presupuestos máximos razonables** que ofrecen un **margen de tolerancia de +20% a +35%** sobre la medición real documentada, manteniendo la exigencia de que la reducción porcentual supere el 40% frente al commit base:

### 3.2. Tabla de Presupuestos y Márgenes

| Componente Medido | Referencia Base (Commit 454601d) | Medición Real Documentada | Presupuesto Máximo Autorizado | Margen sobre Medición Real | Reducción Mínima Garantizada |
|---|:---:|:---:|:---:|:---:|:---:|
| **Instrucción de Sistema (Caracteres)** | 5.951 | 2.273 | **3.000** | +32,0% | **> 49,5%** (frente a base) |
| **Instrucción de Sistema (Bytes UTF-8)** | 6.036 | 2.304 | **3.100** | +34,5% | **> 48,6%** (frente a base) |
| **Declaraciones de Herramientas (Caracteres)** | N/A | 490 | **650** | +32,6% | Cota de seguridad |
| **Declaraciones de Herramientas (Bytes UTF-8)** | N/A | 495 | **670** | +35,3% | Cota de seguridad |
| **Respuesta de Herramienta - Caso IP (Caracteres)** | N/A | 1.123 | **1.500** | +33,5% | Cota de seguridad |
| **Respuesta de Herramienta - Caso IP (Bytes UTF-8)** | N/A | 1.132 | **1.550** | +36,9% | Cota de seguridad |

### 3.3. Criterios de Salvaguarda
- **No reducción artificial**: En ningún caso se abreviaron prompts ni se sacrificó claridad semántica para forzar el cumplimiento de los límites.
- **Constantes históricas preservadas**: Las constantes `BASELINE_BUILD_SYSTEM_INSTRUCTION_CHARS` (5951) y `BASELINE_BUILD_SYSTEM_INSTRUCTION_BYTES` (6036) se mantienen congeladas en código como referencia histórica del commit `454601d`.

---

## 4. Requisitos y Condiciones para Futuras Pruebas Reales con Gemini

Para cuando se decida ejecutar validaciones con la API en vivo de Gemini, se deben observar estrictamente las siguientes directivas:

1. **Prohibición de `count_tokens`**:  
   No se debe utilizar el método `count_tokens` de la API de Gemini como mecanismo de medición ni estimación previa. Dicho método agrega solicitudes de red redundantes, no refleja con exactitud la tarificación final del turno ni los tokens generados, e introduce latencia en la ejecución.
2. **Auditoría directa de `usage_metadata`**:  
   La medición en vivo debe extraerse directamente del bloque `usage_metadata` devuelto por el objeto de respuesta de `generate_content`.
3. **Trazabilidad de Cobertura en Vivo**:  
   Se debe registrar si el proveedor omite o reporta campos en tiempo real (`complete`, `partial`, `unavailable`), auditando si `prompt_token_count`, `candidates_token_count` o `total_token_count` vienen nulos.
4. **Aislamiento en Suites Automatizadas**:  
   Todas las pruebas continuas de regresión en CI/Docker deben seguir ejecutándose con `DETECTIVE_SKIP_DOTENV=1` y credenciales vacías, garantizando que ninguna prueba automatizada dependa de la red ni consuma cuota externa.
