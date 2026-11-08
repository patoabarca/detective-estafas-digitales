# Auditoría y Corrección de Privacidad: Evidencia de Parámetros Sensibles en URLs

## 1. Contexto e Hipótesis Evaluada

Durante la revisión técnica del especialista **Analizador de Enlaces** y su herramienta `tool_analizar_url` posterior a la integración del piloto en `main`, se identificó una posible fuga de privacidad hacia el modelo externo (Google Gemini API):
- La función interna `_extract_concrete_evidence(raw_url, domain, finding_text)` en `agents/tools/url_analysis_tools.py` extrae fragmentos literales de la URL para respaldar cada hallazgo (`UrlSignalFinding`).
- Cuando se detectan parámetros sospechosos en una consulta (regla `INFO-URL-SENSITIVE-PARAMS`), `_extract_concrete_evidence` devuelve la cadena `parsed.query` aislada (por ejemplo, `token=SECRETO_FICTICIO_123&x=1`).
- La hipótesis señalaba que, si dicha evidencia era procesada por `sanitize_url_for_external_llm` (diseñada originalmente para URLs completas estructuradas), una cadena de consulta aislada sin el carácter `@` ni delimitadores de ruta (`/` o `?`) podría atravesar el sanitizador sin enmascarar su valor sensible, exponiéndolo en el campo `function_response` entregado al LLM.

---

## 2. Comprobación y Causa Raíz

### 2.1 Reproducción Automatizada
La hipótesis fue confirmada mediante una prueba de regresión antes de modificar el código productivo (`test_regression_url_query_evidence_leak_without_at_symbol` en `tests/test_analizador_enlaces_pilot.py`):
1. **A nivel de función:** `sanitize_url_for_external_llm("token=SECRETO_FICTICIO_123&x=1")` devolvía literalmente `"token=SECRETO_FICTICIO_123&x=1"` con `redactions_count = 0`.
2. **A nivel de herramienta:** `execute_tool_analizar_url` exponía `"evidencia": "token=SECRETO_FICTICIO_123&x=1"` en `results[0]["senales_encontradas"]`.
3. **A nivel de ciclo del agente:** La captura profunda de los mensajes enviados al cliente simulado (`contents`) contenía el secreto en texto plano.

### 2.2 Causa Raíz Técnica
En `agents/common/privacy.py`, la función `sanitize_url_for_external_llm` operaba bajo el siguiente esquema:
```python
has_scheme = "://" in working
parts = urlsplit(working if has_scheme else f"http://{working}")
```
Al recibir una cadena como `token=SECRETO_FICTICIO_123&x=1`:
1. `has_scheme` resultaba `False`, por lo que se analizaba `http://token=SECRETO_FICTICIO_123&x=1`.
2. Conforme al estándar RFC 3986 y la implementación de `urllib.parse.urlsplit`, al no existir barra inclinada (`/`), signo de interrogación (`?`) ni numeral (`#`), la totalidad de la cadena `token=SECRETO_FICTICIO_123&x=1` era clasificada dentro del campo `netloc` (nombre de host/autoridad).
3. `parts.path`, `parts.query` y `parts.fragment` quedaban como cadenas vacías `""`.
4. El sanitizador únicamente inspeccionaba `netloc` en búsqueda del carácter `@` para detectar credenciales embebidas (`user:pass@host`). Al carecer de `@`, `netloc` no se modificaba.
5. `_redact_url_component` solo se ejecutaba sobre `parts.path`, `parts.query` y `parts.fragment`. Dado que todos estaban vacíos, la sanitización era omitida por completo.
6. `rebuilt` reconstruía la cadena sin modificaciones, retornando el secreto intacto.

---

## 3. Alcance de la Solución Implementada

La corrección se diseñó bajo los principios de mínima intervención, suficiencia técnica y preservación de contratos:

### 3.1 Módulo `agents/common/privacy.py`
1. **Soporte de componentes en `sanitize_url_for_external_llm`:**
   Cuando la entrada carece de esquema explícito (`not has_scheme`), se aplica preventivamente `_redact_url_component(netloc)`. De este modo, cualquier fragmento de consulta, clave-valor o segmento aislado asignado por `urlsplit` a `netloc` es inspeccionado contra las expresiones regulares de parámetros sensibles (`URL_SENSITIVE_PARAM_REGEX`), rutas con identificadores, correos, CBU/CVU, etc.
2. **Función complementaria exportada:**
   Se incorporó y exportó formalmente:
   ```python
   def sanitize_url_component_for_external_llm(component: str) -> Tuple[str, int]:
       """
       Oculta credenciales, parámetros sensibles, tokens de ruta y datos sensibles
       en un componente, fragmento o evidencia de URL aislada (query, netloc, path, userinfo).
       Devuelve el componente sanitizado y la cantidad de ocultamientos aplicados.
       """
       if not component:
           return "", 0
       return sanitize_url_for_external_llm(component)
   ```

### 3.2 Módulo `agents/tools/url_analysis_tools.py`
1. En `_build_sanitized_item_for_llm(item)`:
   - Se procesa `s.evidencia` con `sanitize_url_component_for_external_llm`.
   - Se asegura que tanto las evidencias de señales como las descripciones y advertencias (`item.advertencias`) sean sanitizadas antes de transmitirse al modelo en `function_response`.
2. En `execute_tool_analizar_url`:
   - Se aplica `sanitize_url_component_for_external_llm` a las advertencias generales de la sesión (`url_state.warnings`).
3. **Preservación de Evidencia Local y Contratos:**
   - En memoria local (`UrlItemAnalysisResult.senales_encontradas` y `UrlAnalysisResult`), la evidencia literal (`s.evidencia`) permanece 100% inalterada, asegurando que la auditoría forense interna y la validación de contratos (`result.validate()`, que exige correspondencia exacta entre la evidencia y la URL original) funcionen sin desajustes.
   - No se alteró ninguna regla de detección ni se reasignaron ponderaciones de riesgo.

---

## 4. Matriz de Pruebas Parametrizadas

Se incorporó en `tests/test_analizador_enlaces_pilot.py` una suite de pruebas parametrizadas con datos ficticios (`test_parameterized_url_query_privacy_and_local_evidence_preservation`) y captura de copias profundas (`copy.deepcopy`) en el cliente simulado en el momento exacto de la llamada (`generate_content`), cubriendo:

| Caso de Prueba | URL / Query Evaluada | Elementos Sensibles Ocultos | Tokens Inocuos Preservados | Resultado |
| :--- | :--- | :--- | :--- | :--- |
| **1. Aislado sin `@`** | `https://ejemplo.com/ruta?token=SECRETO_FICTICIO_123&x=1` | `token=[VALOR_URL_OCULTO]` | `token=`, `x=1` | APROBADO |
| **2. Múltiples sensibles + 1 no sensible** | `https://ejemplo.com/api?token=TOKEN_A&clave=CLAVE_B&user=USER_C&page=2` | `token=[VALOR_URL_OCULTO]`, `clave=[VALOR_URL_OCULTO]`, `user=[VALOR_URL_OCULTO]` | `token=`, `clave=`, `user=`, `page=2` | APROBADO |
| **3. Valores con percent-encoding** | `https://ejemplo.com/auth?token=SECRETO%20ESPACIO%20123&pwd=CLAVE%21%23&sort=asc` | `token=[VALOR_URL_OCULTO]`, `pwd=[VALOR_URL_OCULTO]` | `token=`, `pwd=`, `sort=asc` | APROBADO |
| **4. Credenciales con email y userinfo** | `https://usuario_admin:clave_super_secreta_999@servidor-sospechoso.com/panel?email=victima@empresa.com&token=XYZ_TOKEN_SECRETO_123&seccion=perfil` | `[CREDENCIAL_URL_OCULTA]`, `email=[VALOR_URL_OCULTO]`, `token=[VALOR_URL_OCULTO]` | `servidor-sospechoso.com`, `seccion=perfil` | APROBADO |
| **5. URL sin parámetros sensibles** | `https://ejemplo.com/seguro?categoria=noticias&seccion=general&page=3` | Ninguno (`redactions_count = 0`) | `categoria=noticias`, `seccion=general`, `page=3` | APROBADO |
| **6. Conservación de evidencia local** | Verificación en los 5 casos anteriores | Evidencia local intacta | `result.validate()` exitoso | APROBADO |

---

## 5. Límites y Alcance de las Pruebas

### 5.1 Qué Garantiza la Suite Simulada
- Que ninguna solicitud estructurada ni respuesta de herramienta transmitida al cliente LLM (`contents`) exponga los valores de parámetros sensibles o credenciales previstos en las expresiones regulares del proyecto (`URL_SENSITIVE_PARAM_REGEX`).
- Que los nombres de los parámetros y la estructura sintáctica de las consultas no se destruyan, permitiendo al modelo comprender el tipo de técnica empleada.
- Que la evidencia literal persista íntegra en la memoria local de la aplicación para respaldar auditorías forenses y contratos estrictos.
- Que no existan regresiones en los 154 casos de prueba del proyecto (suite offline ejecutada en su totalidad).

### 5.2 Qué Requeriría una Validación de Producción
- **Calidad de inferencia con tokens enmascarados:** Verificar con tráfico real hacia Gemini que la presencia del marcador `[VALOR_URL_OCULTO]` en la evidencia de la herramienta sea interpretada naturalmente por el modelo en su síntesis de texto final, sin alucinar explicaciones anómalas.
- **Nombres de parámetros atípicos:** Las expresiones regulares cubren los nombres de parámetros más comunes en flujos de autenticación y estafas (`token`, `auth`, `clave`, `pwd`, `otp`, `pin`, `cbu`, `cvu`, `session`, `key`, `secret`, etc.). En entornos de producción con esquemas propietarios de API, parámetros no tipificados requerirían enriquecimiento de la lista o inspección heurística adicional.
- **Auditoría de logs en la nube:** Monitoreo periódico de los registros del proyecto en Google Cloud Vertex AI / AI Studio para certificar que ningún payload de usuario escape a las políticas de Data Loss Prevention (DLP).
