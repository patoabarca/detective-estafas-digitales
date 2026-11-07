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

### 2.2 Medición Real del Contexto Efectivo de `build_system_instruction()`

Medición obtenida ejecutando directamente el método `build_system_instruction()` de cada agente, usando sus respectivos cargadores y archivos `SKILL.md` sin fórmulas alternativas:

| Métrica Efectiva | Versión Base (`454601d`) | Versión Piloto Actual | Diferencia Absoluta | Reducción (%) |
| :--- | :---: | :---: | :---: | :---: |
| **Caracteres Efectivos** | **5.951** caracteres | **3.457** caracteres | **-2.494 caracteres** | **-41,91 %** |
| **Bytes UTF-8 Efectivos** | **6.036** bytes | **3.513** bytes | **-2.523 bytes** | **-41,80 %** |

*Causa técnica de las variaciones previas:*
- Cuando se medía únicamente la concatenación cruda sin el formateador de sección de skills (`format_skills_prompt_section`), las cifras daban 5.515 caracteres crudos (5.592 bytes) para la base y 3.177 caracteres (3.228 bytes) para el piloto.
- Sin embargo, lo que efectivamente se envía al modelo en el bucle de herramientas (`run_agent_tool_loop`) es la salida completa de `build_system_instruction()`, que incorpora los encabezados y metadatos de la skill cargada. Las cifras definitivas y exactas de contexto entregado a la API son **5.951 caracteres (6.036 bytes)** en la base frente a **3.457 caracteres (3.513 bytes)** en el piloto, logrando una reducción real de **2.494 caracteres (-41,91%)** y **2.523 bytes UTF-8 (-41,80%)**.

---

## 3. Alcance de las Verificaciones

### 3.1 Privacidad y Enmascaramiento de Datos
- **Alcance comprobado:** Se validó que las credenciales en netloc (`usuario:clave@host`) se sustituyan por `[CREDENCIAL_URL_OCULTA]` y que parámetros sensibles comunes (`token`, `clave`, `password`, `email`) en query/path se sustituyan por `[VALOR_URL_OCULTO]`. En la prueba automatizada, ninguno de los secretos pasó en texto claro al historial de mensajes enviado al cliente del modelo.
- **Delimitación explícita:** En coincidencia con la advertencia técnica de `agents/common/privacy.py`, este enmascaramiento por expresiones regulares **reduce la exposición de datos frecuentes en los recorridos probados, pero no constituye una garantía universal** contra fugas en texto libre arbitrario o parámetros no estandarizados.

### 3.2 Pruebas Independientes de Git y Equivalencia Funcional
- La suite [`tests/test_analizador_enlaces_pilot.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/tests/test_analizador_enlaces_pilot.py) prescinde totalmente de comandos `git` en tiempo de ejecución, permitiendo que la suite corra dentro de imágenes Docker limpias sin binario ni historial de Git.
- **Dataset de referencia congelado:** Se incorporó el diccionario `BASELINE_REFERENCE_RESULTS_COMMIT_454601d`, que contiene los resultados completos y exactos generados por la versión base sobre los casos ficticios (`caso_ip`, `caso_tld`, `caso_legitimo`, `caso_multiples_mixto`, `caso_sin_enlaces`).
- **Commit de origen:** `454601ddb6259bcec2b77f5ee6478649dd9f183f`.
- **Procedimiento de regeneración reproducible:**
  ```python
  # Extraer la clase base y el SKILL.md original desde el commit 454601d:
  base_agent_code = subprocess.check_output(['git', 'show', '454601d:agents/analizador_enlaces/agent.py'], text=True)
  base_skill_code = subprocess.check_output(['git', 'show', '454601d:.agents/skills/analizar-url/SKILL.md'], text=True)
  # Instanciar el agente base con ScriptedMockLLMClient y ejecutar sobre los casos.
  ```
- **Campos comparados:** Se valida la igualdad estricta de `estado`, `detalle_estado`, `intervino_agente`, `cantidad_enlaces_extraidos`, `cantidad_enlaces_procesados`, `enlaces_omitidos`, `advertencias`, `skills_cargadas`, `herramientas_invocadas`, y para cada enlace `url_id`, `masked_url`, `estado_enlace` y `reglas_activadas`.

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
- **Ejecuciones del script:** **2 ejecuciones locales**, ambas con salida de error (exit code 1) por fallo de serialización local en `json.dump()`.
- **Solicitudes reales al modelo (HTTP/API):** El total exacto de solicitudes HTTP cursadas a nivel de red **no está verificado**, ya que no existen registros de tráfico crudo ni logs de red de la primera corrida que permitan acreditarlo fehacientemente. En la segunda corrida, la conversación completó 2 turnos registrados por el agente (solicitud inicial y respuesta de herramienta).
- **Turnos del modelo por conversación:** **2 turnos** registrados en la segunda interacción.
- **Reintentos del cliente:** **0 reintentos** reportados en la segunda corrida. En esa interacción la API respondió en el primer intento sin errores HTTP ni desconexiones.

### 4.3 Explicación del Archivo `real_pilot_execution_result.json`
- **Motivo de la creación manual:** Para no violar la directiva de no repetir automáticamente la prueba completa ni generar tráfico adicional hacia la API tras los 2 intentos ya cursados, se utilizó la herramienta `write_file` para generar el archivo JSON en `scratch/` a partir de las líneas registradas en stdout de la segunda corrida.
- **Campos verificados fehacientemente (respaldados por stdout original de la 2ª corrida):**
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
  - **Total exacto de solicitudes HTTP cursadas:** No está verificado por ausencia de telemetría de red en la primera corrida.
  - **Métricas de la 1ª corrida:** No existen registros de tiempo ni consumo en stdout para la primera corrida (finalizada en línea 89 antes de cualquier print).
  - **Desglose de prompt vs. output tokens en la 2ª corrida:** El stdout mostró `Prompt=0, Output=0, Total=3022`. La API en este endpoint acumuló el total sin desglosar componentes en la estructura consumida por el tracer. Cualquier desglose es **NO VERIFICADO**.
  - **Argumentos de herramienta en el tracer:** En stdout figuró `Tool llamada: None con args: None` debido a un desacople de nombres en el script de prueba (`tc.get('name')` en vez de los campos del tracer). Aunque el contrato final certificó la invocación de `tool_analizar_url`, el log del tracer para esa llamada quedó incompleto en stdout.

---

## 5. Validación Aislada en Docker

Se ejecutó la validación completa en contenedores de acuerdo a los requerimientos de aislamiento estricto:

### 5.1 Construcción de Imagen
- **Etiqueta dedicada:** `detective-estafas-digitales:piloto-refactor`
- **Comando:** `docker build -t detective-estafas-digitales:piloto-refactor .`
- **Inspección de módulos:**
  - Presencia verificada de `agents/analizador_enlaces/agent.py` (6.403 bytes), `prompts.py` (4.708 bytes) y `result_builder.py` (6.874 bytes).
  - Presencia verificada de `.agents/skills/analizar-url/SKILL.md` (1.608 bytes) y `references/url_signals_guide.md` (4.635 bytes).

### 5.2 Pruebas en Contenedor Offline (Zero Network)
- **Ejecución aislada de la suite:**
  `docker run --rm --network none --entrypoint pytest detective-estafas-digitales:piloto-refactor -v -k "not test_real_gemini_api"`
- **Resultado:** **148 pruebas aprobadas, 1 deseleccionada condicional en 3.95s**.
- **Independencia de red:** La bandera `--network none` certificó que ninguna prueba requiere conectividad a internet ni interactúa con la API de Gemini.

### 5.3 Arranque y Verificación de Streamlit
- **Instancia temporal aislada:**
  - Nombre: `detective-piloto-test`
  - Puerto mapeado: `127.0.0.1:8503 -> 8501/tcp` (puerto 8503 libre).
  - Sin volúmenes montados de `output/` ni variables de credenciales inyectadas.
- **Verificación de logs:** Uvicorn y Streamlit iniciaron correctamente en `0.0.0.0:8501`.
- **Sondeo HTTP:** `Invoke-WebRequest -Uri "http://127.0.0.1:8503"` respondió con código **200 OK**.
- **Limpieza:** El contenedor temporal `detective-piloto-test` fue detenido y eliminado inmediatamente tras la prueba.
- **Contenedores preexistentes:** El contenedor en producción `detective-estafas-web` (puerto 8502) y la aplicación HomeLens permanecieron activos y completamente inalterados.

---

## 6. Estado de la Rama y Cierre Técnico

- **Rama:** `refactor/piloto-analizador-enlaces`
- **Etiquetas preservadas:** `v2.0-orquesta-presentada` intacta sobre `454601ddb6259bcec2b77f5ee6478649dd9f183f`.
- **Cambios locales ajenos conservados:** `compose.yaml` (modificación local no commiteada en línea 6) y `~$Orquesta_Agentes_y_Skills.pptx` (archivo temporal).
- **Alcance preservado:** Sin modificaciones en los demás agentes (`preparador`, `analizador_mensajes`, `evaluador`).
- **Estado de la suite:** 148 pruebas aprobadas tanto localmente como en Docker.
