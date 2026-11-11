---
name: detectar-amenazas
description: >-
  Detecta amenazas explícitas o implícitas de bloqueo, suspensión, baja de cuenta,
  cierre de servicio, retención de envíos o consecuencias legales/patrimoniales.
tool_name: tool_detectar_amenazas
allowed_agents:
  - analizador_mensajes
---

# Skill: Detectar Amenazas (`detectar-amenazas`)

## Instrucciones Operativas de `tool_detectar_amenazas`
1. **Ejecución:** Invocá `tool_detectar_amenazas` con `confirm_session_text=true` sobre el texto preparado en sesión para evaluar la categoría `"amenazas"` (`ING-AMENAZA-BLOQUEO`).
2. **Estado y errores:** Devuelve `status="ok"` (`detected=true/false`) o `status="tool_error"` si falta texto preparado o falla la ejecución.
3. **Límites:** Evaluá solo amenazas de bloqueo, suspensión, retención o intimación; no inventes evidencia literal, no analices URLs ni asignes riesgo final.
