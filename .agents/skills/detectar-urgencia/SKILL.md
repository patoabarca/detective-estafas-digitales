---
name: detectar-urgencia
description: >-
  Detecta expresiones de presión temporal, plazos perentorios o urgencia artificial
  diseñados para forzar decisiones apresuradas en mensajes potencialmente fraudulentos.
tool_name: tool_detectar_urgencia
allowed_agents:
  - analizador_mensajes
---

# Skill: Detectar Urgencia (`detectar-urgencia`)

## Instrucciones Operativas de `tool_detectar_urgencia`
1. **Ejecución:** Invocá `tool_detectar_urgencia` con `confirm_session_text=true` sobre el texto preparado en sesión para evaluar la categoría `"urgencia"` (`ING-URGENCIA-ARTIFICIAL`).
2. **Estado y errores:** Devuelve `status="ok"` (`detected=true/false`) o `status="tool_error"` si falta texto preparado o ocurre un fallo técnico.
3. **Límites:** Evaluá solo urgencia temporal; no inventes evidencia fuera de los fragmentos devueltos, no analices URLs ni asignes riesgo final.
