---
name: analizar-url
description: >-
  Audita de forma estática la estructura sintáctica de las URLs extraídas en la sesión
  actual mediante tool_analizar_url, sin visitar enlaces ni consultar la red.
tool_name: tool_analizar_url
allowed_agents:
  - analizador_enlaces
---

# Skill: Analizar Estructura de URLs (`analizar-url`)

## Instrucciones Operativas de `tool_analizar_url`
1. **Procesamiento en lote:** Invocá `tool_analizar_url` pasando en `url_ids` la lista completa de identificadores de la sesión (ej. `["URL-1", "URL-2"]` o `["ALL"]`) en una sola llamada para auditar todos los enlaces disponibles.
2. **Uso estricto de identificadores:** Utilizá EXCLUSIVAMENTE los identificadores de sesión provistos (`URL-n`). Nunca inventes identificadores, no sustituyas enlaces y no intentes autocorregir direcciones dudosas provenientes de OCR.
3. **Cero Red (Zero Network):** El análisis es 100% estático sobre la cadena de texto de la URL. Jamás intentes navegar, resolver DNS ni realizar solicitudes HTTP.
4. **Interpretación prudente:** La ausencia de señales sintácticas en un enlace NO garantiza que el sitio web sea legítimo o seguro.
