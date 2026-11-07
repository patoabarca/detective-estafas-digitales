# Documentación de Validación del Piloto: Analizador de Enlaces y Skill `analizar-url`

**Rama de trabajo:** `refactor/piloto-analizador-enlaces`  
**Commit base:** `454601ddb6259bcec2b77f5ee6478649dd9f183f` (etiqueta `v2.0-orquesta-presentada`)  
**Fecha:** Noviembre 2026  

---

## 1. Objetivo y Alcance del Piloto

El objetivo de este piloto es validar en un componente delimitado (`AnalizadorEnlacesAgent` y su skill `analizar-url`) la separación rigurosa de responsabilidades solicitada para la arquitectura de agentes y skills:
1. **Delimitar la estructura del Agente**:
   - `agent.py`: Coordinación del ciclo de ejecución, registro de trazas y manejo del ciclo de vida.
   - `prompts.py`: Instrucciones de sistema base, esquemas JSON Schema de herramientas y construcción del prompt de usuario con bloques no confiables sanitizados (`<untrusted_urls>`).
   - `result_builder.py`: Conversión de resultados de herramientas, validación de esquemas y construcción estricta del contrato `UrlAnalysisResult`.
2. **Aligerar la Skill (`SKILL.md`)**:
   - Reducir `SKILL.md` exclusivamente a instrucciones operativas esenciales, restricciones de seguridad y directivas de ejecución.
   - Trasladar el catálogo extenso de reglas y señales a una guía técnica de referencia (`references/url_signals_guide.md`) para consumo y auditoría humana, sin simular cargas dinámicas inexistentes.
3. **Preservar el Principio de Fuente Única de Verdad**:
   - Mantener el motor determinístico en `scripts/url_analyzer.py` y `agents/tools/url_analysis_tools.py`, garantizando paridad total entre el análisis local y la orquesta.
4. **Garantizar Cero Fugas de Datos Sensibles**:
   - Comprobar que credenciales embebidas (`user:pass@host`) y parámetros sensibles de consulta o rutas se enmascaren antes de ser enviados al modelo externo o registrados en las herramientas.

---

## 2. Métricas Comparativas: Antes vs. Después

La línea base fue congelada a partir del commit de la versión presentada `454601d`.

| Métrica de Contexto | Versión Base (`v2.0-orquesta-presentada`) | Versión Piloto Modularizada | Diferencia Absoluta | Variación (%) |
| :--- | :---: | :---: | :---: | :---: |
| **Caracteres Instrucción Sistema** | 5.958 caracteres | 3.464 caracteres | **-2.494 caracteres** | **-41,9 %** |
| **Bytes UTF-8 Instrucción Sistema** | 6.022 bytes | 3.499 bytes | **-2.523 bytes** | **-41,9 %** |
| **Líneas de Código en `agent.py`** | 280 líneas | 142 líneas | **-138 líneas** | **-49,3 %** |
| **Separación Modular** | Monolito en `agent.py` | 3 módulos especializados | prompts / builder / agent | Modular |

### Verificación de Equivalencia Funcional
En el conjunto de casos sintéticos de prueba (`tests/test_analizador_enlaces_pilot.py`), se comprobó la **equivalencia del 100% de los campos funcionales del contrato**:
- `estado` y `detalle_estado`.
- `cantidad_enlaces_extraidos` y `cantidad_enlaces_procesados`.
- `enlaces_omitidos` y `advertencias`.
- Identificadores de reglas detectadas (`REGLA-URL-01`, `REGLA-URL-05`, etc.).
- Preservación de la advertencia mandatoria cuando un enlace no presenta señales de riesgo sintáctico (*"sin señales no garantiza legitimidad"*).

---

## 3. Aclaración Metodológica: Mensajes sin Enlaces

Durante los ensayos del benchmark de aislamiento, surgió la duda sobre por qué el especialista registraba dos turnos cuando se le entregaba una lista vacía de URLs:

1. **Invocación Unitaria Directa del Especialista (`AnalizadorEnlacesAgent.run`)**:
   - Cuando se prueba al agente en aislamiento con `extracted_urls=[]`, el agente inicia su ciclo de herramientas con el LLM.
   - El LLM emite una llamada a `tool_analizar_url(url_ids=["ALL"])`.
   - La herramienta local responde `{"status": "no_links", "processed_count": 0}`.
   - El modelo emite el texto de cierre, consumiendo **2 turnos simulados**.
2. **Flujo Integral de la Orquesta (`OrquestadorAgent.run`)**:
   - En la orquestación real, el Agente Orquestador evalúa la salida del Agente Preparador.
   - Si `len(preparacion.enlaces_encontrados) == 0`, el Orquestador **omite completamente la invocación al Analizador de Enlaces** (`_build_omitted_url_analysis_result()`).
   - Se registra `intervino_agente=False`, `detalle_estado="sin_enlaces"` y evento `agent_skipped`.
   - **Consumo en la orquesta:** 0 llamadas de modelo y 0 llamadas a herramientas para enlaces.

---

## 4. Enmascaramiento y Seguridad de Datos

Se incorporó la prueba reproducible `test_url_privacy_sanitization_in_prompt_and_tool_exchange` que valida:
1. Las credenciales embebidas (`https://user:password@host/path`) se sustituyen por `[CREDENCIAL_URL_OCULTA]`.
2. Los parámetros sensibles de consulta (`token=...`, `clave=...`, `password=...`, `email=...`) se reemplazan por `[VALOR_URL_OCULTO]`.
3. Ningún valor secreto original aparece en el texto del prompt, en los argumentos de herramientas ni en el historial `contents` enviado al proveedor externo.

---

## 5. Resultados de la Ejecución Real Autorizada (Gemini)

Se ejecutó una única prueba real con el modelo configurado en el entorno (`gemini-3.5-flash-lite`), analizando un caso sintético con dos URLs:
- `URL-1`: `https://promocion-aniversario.xyz/premio` (sospechosa por extensión TLD inusual).
- `URL-2`: `https://portal-seguro.ejemplo.com/contacto` (dominio corporativo simulado sin señales).

### Métricas Observadas en la API:
- **Modelo utilizado:** `gemini-3.5-flash-lite`
- **Duración total:** 2,98 segundos
- **Turnos del modelo:** 2 turnos
  - *Turno 1:* El modelo analizó el prompt con `<untrusted_urls>` e invocó `tool_analizar_url(url_ids=['ALL'])` en lote.
  - *Turno 2:* Recibió la respuesta de la herramienta local y emitió la síntesis explicativa final.
- **Llamadas a herramientas:** 1 llamada a `tool_analizar_url` en lote.
- **Reintentos del cliente:** 0 reintentos.
- **Consumo de tokens informado:** Total = 3.022 tokens.
- **Resultado del contrato:**
  - `estado`: `correcto`
  - `detalle_estado`: `analizados_con_senales`
  - `cantidad_enlaces_procesados`: 2 / 2
  - `URL-1`: detectó `REGLA-URL-05` (`.xyz`, riesgo TLD sospechoso).
  - `URL-2`: clasificado como `analizado_sin_senales` con advertencia de prudencia.
  - Esquema y tipos del contrato `UrlAnalysisResult`: 100% válidos.

---

## 6. Estado de Git y Límites de la Rama

- **Rama actual:** `refactor/piloto-analizador-enlaces`
- **Etiqueta intacta:** `v2.0-orquesta-presentada` sobre `454601ddb6259bcec2b77f5ee6478649dd9f183f`.
- **Modificación ajena preservada:** `compose.yaml` (línea 6) no ha sido modificada, descartada ni commiteada.
- **Archivos temporales:** El archivo temporal `~$Orquesta_Agentes_y_Skills.pptx` se mantiene sin versionar.
- **Total de pruebas automatizadas en verde:** 148 pruebas aprobadas (1 deseleccionada condicional de integración orquesta).
