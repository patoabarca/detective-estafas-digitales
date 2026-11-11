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

# Skill: Extraer Enlaces (`extraer-enlaces`)

## Instrucciones Operativas de `tool_extraer_enlaces`
1. **Ejecución:** Invocá `tool_extraer_enlaces` (opcionalmente `include_static_metadata=true`) sobre el texto activo validado en la sesión (directo o extraído por OCR).
2. **Interpretación de estado:**
   - `status="ok"`: se detectaron URLs y quedaron registradas como `URL-1`, `URL-2`, ... para su auditoría posterior.
   - `status="no_links"`: texto revisado sin enlaces; es un resultado normal y válido.
   - `status="tool_error"`: reportá el fallo técnico.
3. **Límites estrictos:**
   - **Zero Network:** jamás abras, resuelvas DNS ni hagas peticiones HTTP a las URLs encontradas.
   - **Sin análisis de riesgo:** no evalúes reglas `REGLA-URL-*` en esta etapa (corresponde al Agente Analizador de Enlaces).
