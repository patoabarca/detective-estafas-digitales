# Documentación de Validación del Piloto: Analizador de Enlaces y Skill `analizar-url`

**Rama de trabajo:** `refactor/piloto-analizador-enlaces`  
**Commit base:** `454601ddb6259bcec2b77f5ee6478649dd9f183f` (etiqueta `v2.0-orquesta-presentada`)  
**Fecha:** Noviembre 2026  

---

## 1. Objetivo y Alcance del Piloto

El objetivo de este piloto es validar en un componente delimitado (`AnalizadorEnlacesAgent` y su skill `analizar-url`) la separación rigurosa de responsabilidades para la arquitectura de agentes y skills:
1. **Delimitar la estructura del Agente**:
   - `agent.py`: Coordinación del ciclo de vida del agente, registro de trazas y ejecución del bucle de herramientas.
   - `prompts.py`: Instrucciones de sistema base, esquemas JSON Schema de herramientas autorizadas y construcción del prompt de usuario con bloques no confiables sanitizados (`<untrusted_urls>`).
   - `result_builder.py`: Conversión de respuestas de herramientas, validación de esquemas y construcción estricta del contrato `UrlAnalysisResult`.
2. **Aligerar la Skill (`SKILL.md`)**:
   - Reducir `SKILL.md` exclusivamente a instrucciones operativas esenciales, restricciones de seguridad y directivas de ejecución.
   - Trasladar el catálogo extenso de reglas y señales a una guía técnica de referencia (`references/url_signals_guide.md`) para consumo y auditoría humana, sin simular mecanismos de carga dinámica inexistentes.
3. **Preservar la Fuente Única de Verdad**:
   - Mantener el motor determinístico en `scripts/url_analyzer.py` y `agents/tools/url_analysis_tools.py`, asegurando que el modo local y la orquesta compartan exactamente las mismas reglas y ponderaciones.
4. **Verificación Acotada de Privacidad**:
   - Comprobar que credenciales en netloc (`user:pass@host`) y parámetros sensibles conocidos en query/path se enmascaren en los recorridos probados antes de enviar datos al LLM.

---

## 2. Mediciones Comparativas: Commit Base `454601d` vs. Piloto

### 2.1 Conteo de Líneas de Código (LOC)

Medición estricta realizada sobre el commit base `454601d` y la rama de trabajo actual:

| Componente | Líneas Totales | Líneas No Vacías | Rol / Responsabilidad |
| :--- | :---: | :---: | :--- |
| **`agent.py` Base (`454601d`)** | **362** | **328** | Monolito (instrucciones, schemas, bucle y contrato) |
| **`agent.py` Piloto** | **168** | **149** | Exclusivamente coordinación, ciclo de vida y trazas |
| **`prompts.py` Piloto** | **89** | **77** | Instrucciones base, schema JSON y prompt builder |
| **`result_builder.py` Piloto** | **167** | **153** | Validación y construcción de `UrlAnalysisResult` |
| **Total Agente Piloto (3 módulos)** | **424** | **379** | Módulos desacoplados con contratos tipados |

*Aclaración de inconsistencias previas:*
- La cifra de **362 líneas** corresponde a las líneas totales del `agent.py` original en `454601d` (con **328 líneas no vacías**).
- La mención anterior de "280 líneas" fue una estimación informal inexacta no verificada por contador de líneas.
- En la versión modularizada, `agent.py` se redujo a **168 líneas totales** (**149 no vacías**), una disminución del **53,6%** en el archivo principal. El conjunto de los 3 módulos suma 424 líneas debido a la formalización de imports independientes, docstrings de módulo y tipado estricto.

---

### 2.2 Medición del Contexto de Instrucción de Sistema

Se ejecutó el mismo procedimiento automatizado de cálculo en Python para ambos estados:
`instruccion_completa = f"{BASE_INSTRUCTIONS}\n\n{SKILL_BODY}".strip()`

| Representación del Texto | Base (`454601d`) | Piloto Actual | Diferencia Absoluta | Reducción (%) |
| :--- | :---: | :---: | :---: | :---: |
| **Texto plano original (raw chars)** | 5.515 caracteres | 3.177 caracteres | **-2.338 caracteres** | **-42,39 %** |
| **Bytes UTF-8 originales** | 5.592 bytes | 3.228 bytes | **-2.364 bytes** | **-42,27 %** |
| **JSON serializado (`ensure_ascii=False`) chars** | 5.579 caracteres | 3.217 caracteres | **-2.362 caracteres** | **-42,34 %** |
| **JSON serializado (`ensure_ascii=False`) bytes** | 5.656 bytes | 3.268 bytes | **-2.388 bytes** | **-42,22 %** |
| **JSON con escape ASCII (`ensure_ascii=True`) chars** | 5.960 caracteres | 3.472 caracteres | **-2.488 caracteres** | **-41,74 %** |

*Causa técnica de las discrepancias anteriores:*
Las cifras de ~5.958 y ~3.464 caracteres reportadas previamente provenían de medir cadenas serializadas con `json.dumps(..., ensure_ascii=True)`, que transforma cada vocal acentuada en español (`á`, `é`, `í`, `ó`, `ú`, `ñ`) en su secuencia de escape `\uXXXX` (6 caracteres ASCII por letra). Al medir el texto plano UTF-8 nativo, la reducción real es de **5.515 a 3.177 caracteres (-42,4%)** y de **5.592 a 3.228 bytes (-42,3%)**.

---

## 3. Alcance de las Verificaciones

### 3.1 Privacidad y Enmascaramiento de Datos
- **Alcance comprobado:** Se validó que las credenciales en netloc (`usuario:clave@host`) se sustituyan por `[CREDENCIAL_URL_OCULTA]` y que parámetros sensibles comunes (`token`, `clave`, `password`, `email`) en query/path se sustituyan por `[VALOR_URL_OCULTO]`. En la prueba automatizada, ninguno de los secretos pasó en texto claro al historial de mensajes enviado al cliente del modelo.
- **Delimitación explícita:** En coincidencia con la advertencia técnica de `agents/common/privacy.py`, este enmascaramiento por expresiones regulares **reduce la exposición de datos frecuentes en los recorridos probados, pero no constituye una garantía universal** contra fugas en texto libre arbitrario o parámetros no estandarizados.

### 3.2 Equivalencia Funcional Directa contra la Versión Base
- La suite [`tests/test_analizador_enlaces_pilot.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/tests/test_analizador_enlaces_pilot.py) carga dinámicamente en memoria la clase original `AnalizadorEnlacesAgent` directamente del commit base `454601d` (`git show 454601d:agents/analizador_enlaces/agent.py`).
- Ejecuta en paralelo el agente base y el agente piloto con el mismo cliente simulado y el mismo contexto.
- Comprueba la equivalencia estricta de todos los campos del contrato: `estado`, `detalle_estado`, `cantidad_enlaces_extraidos`, `cantidad_enlaces_procesados`, `enlaces_omitidos` y la lista de `reglas_activadas` por enlace.

---

## 4. Registro y Conciliación de las Ejecuciones Reales (Gemini)

Durante la validación con la API real de Google Gemini (`gemini-3.5-flash-lite`), se produjeron eventos que requieren conciliación rigurosa:

### 4.1 Análisis Post-Mortem de las Corridas del Script `run_real_pilot_execution.py`

1. **Primera ejecución (17:32:09):**
   - **Resultado:** Exit code 1 por excepción en Python.
   - **Causa:** `TypeError: Object of type UrlSignalFinding is not JSON serializable` en la línea 89 al llamar a `json.dump()`.
   - **¿Llegó a Gemini?:** **SÍ**. El método `agent.run()` se ejecutó completamente, completando la conversación con Gemini y poblando el objeto `result` y el `tracer`. El fallo ocurrió después, al intentar guardar el archivo JSON en disco. Como el script no tenía `print` previo a esa línea, no se capturaron métricas en stdout.
2. **Modificación del scratch script:**
   - Se agregaron sentencias `print` de diagnóstico antes del volcado a disco y se convirtió `item.findings` a diccionario con `asdict`. Sin embargo, el campo `"senales_encontradas": item.senales_encontradas` permaneció con instancias `UrlSignalFinding`.
3. **Segunda ejecución (17:33:24):**
   - **Resultado:** Exit code 1 por excepción en Python.
   - **Causa:** Idéntico `TypeError` al serializar `senales_encontradas` en `json.dump()`.
   - **¿Llegó a Gemini?:** **SÍ**. Se realizó una segunda interacción real con Gemini. Gracias a los `print` agregados, los datos de salida del agente se imprimieron en stdout antes de la caída del proceso.

### 4.2 Diferenciación de Conceptos Operativos
- **Ejecuciones del script:** **2 ejecuciones locales**, ambas con salida de error (exit code 1) por fallo de serialización local.
- **Solicitudes reales al modelo (HTTP/API):** **4 solicitudes HTTP en total** (2 solicitudes por cada corrida del agente: Turno 1 con prompt inicial; Turno 2 con la respuesta de la herramienta).
- **Turnos del modelo por conversación:** **2 turnos** en cada interacción.
- **Reintentos del cliente:** **0 reintentos**. En ambas ejecuciones la API respondió en el primer intento sin errores HTTP ni desconexiones.

### 4.3 Explicación del Archivo `real_pilot_execution_result.json`
- **Motivo de la creación manual:** Para no violar la directiva de no repetir automáticamente la prueba completa ni generar tráfico adicional hacia la API tras los 2 intentos ya cursados, se utilizó la herramienta `write_file` para generar el archivo JSON en `scratch/` a partir de las líneas registradas en stdout.
- **Campos verificados fehacientemente (respaldados por stdout original):**
  - Modelo: `gemini-3.5-flash-lite`
  - Duración total de la 2ª interacción: `2.98s`
  - Turnos conversacionales: `2`
  - Herramientas ejecutadas en el ciclo: `1`
  - Reintentos internos: `0`
  - Total de tokens: `3022`
  - Contrato: `estado="correcto"`, `detalle_estado="analizados_con_senales"`, `procesados=2/2`
  - Detección en `URL-1`: `REGLA-URL-05` (evidencia `.xyz`)
  - Clasificación en `URL-2`: `analizado_sin_senales`
- **Campos NO VERIFICADOS (transparencia metodológica):**
  - **Desglose de prompt vs. output tokens:** El stdout mostró `Prompt=0, Output=0, Total=3022`. La API en este endpoint acumuló el total sin desglosar componentes en la estructura consumida por el tracer. Cualquier desglose es **NO VERIFICADO**.
  - **Argumentos de herramienta en el tracer:** En stdout figuró `Tool llamada: None con args: None` debido a un desacople de nombres en el script de prueba (`tc.get('name')` en vez de los campos del tracer). Aunque el contrato final certificó la invocación de `tool_analizar_url`, el log del tracer para esa llamada quedó incompleto en stdout.

---

## 5. Estado de la Rama y Próximos Pasos

- **Rama:** `refactor/piloto-analizador-enlaces`
- **Etiqueta v2.0-orquesta-presentada:** Intacta sobre `454601d`.
- **Modificación pendiente ajena:** `compose.yaml` (línea 6) preservada intacta.
- **Suite de pruebas automatizadas:** 148 pruebas aprobadas (1 deseleccionada condicional).
- **Conclusión del piloto:** La modularización técnica y reducción de contexto quedaron demostradas formalmente. Resta la validación de Docker y la decisión de integración.
