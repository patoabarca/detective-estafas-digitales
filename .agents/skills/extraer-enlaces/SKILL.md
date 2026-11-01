---
name: extraer-enlaces
description: >-
  Identifica y extrae de manera estática todas las direcciones web (URLs) presentes en
  un texto recibido o extraído por OCR, asignándoles identificadores de referencia locales
  sin visitar los enlaces, sin realizar consultas de red y sin evaluar su riesgo.
tool_name: tool_extraer_enlaces
allowed_agents:
  - preparador
---

# 🔗 Skill: Extraer Enlaces (`extraer-enlaces`)

## 1. Única Responsabilidad
Identificar y extraer estáticamente las direcciones web (URLs) presentes en el texto activo del contexto de preparación (`extract_urls`), registrando sus referencias locales (`URL-1`, `URL-2`, ...) para que, si existen enlaces, puedan ser auditados posteriormente por el **Agente Analizador de Enlaces** (`analizador_enlaces`). Esta skill **no realiza el análisis de riesgo de las URLs** ni visita ninguna dirección.

## 2. Qué Recibe (Entrada)
Recibe a través de la herramienta `tool_extraer_enlaces` la solicitud de inspeccionar el texto activo de la sesión (ya sea el texto ingresado por el usuario o el texto extraído por OCR). Opcionalmente acepta el parámetro booleano `include_static_metadata` (mantenido por compatibilidad de firma, por defecto `true`).

## 3. Qué Devuelve (Salida)
Devuelve un diccionario estructurado con:
- `status`: `"ok"` cuando se encontraron uno o más enlaces, `"no_links"` cuando el texto fue revisado correctamente pero no contiene ningún enlace, o `"tool_error"` si ocurrió un error inesperado.
- `links_count`: cantidad entera de enlaces únicos detectados (`0` si no hay enlaces).
- `url_ids`: lista de identificadores estables asignados a cada enlace extraído (`["URL-1", "URL-2", ...]`).
- `urls`: lista de cadenas con las URLs extraídas en su versión sanitizada para el modelo (mientras los enlaces originales sin enmascarar se conservan en el estado local de la sesión).
- `warnings`: advertencias de lectura (incluyendo advertencias de posibles distorsiones tipográficas provenientes del OCR si las hubiera).
- `error_message`: `null` en operación normal, o descripción del fallo si `status == "tool_error"`.

## 4. Herramienta Python Utilizada
- Función registrada: `tool_extraer_enlaces` en `agents/tools/preparation_tools.py`.
- Reutiliza internamente `extract_urls` de `scripts/url_analyzer.py` (únicamente extracción, sin ejecutar `analyze_single_url`).

## 5. Límites y Manejo de Errores
- **Política estricta Zero Network:** la herramienta **nunca** abre, descarga, resuelve por DNS ni envía peticiones HTTP/HTTPS a las URLs encontradas.
- **Separación de responsabilidades:** no evalúa reglas `REGLA-URL-*`; esa tarea corresponde exclusivamente al `Agente Analizador de Enlaces` (`analizar-url`).
- **Diferenciación explícita:** cuando un mensaje no tiene enlaces, devuelve `status: "no_links"` y `urls: []`, lo cual es un resultado válido y normal.
