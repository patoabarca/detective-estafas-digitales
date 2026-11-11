---
name: calcular-puntaje
description: >-
  Calcula en Python el puntaje heurístico de severidad acumulada (0-100) y genera la lista
  de reglas activadas sobre los hallazgos reunidos, aplicando estrictamente las ponderaciones
  documentadas sin que el modelo invente, altere o sume puntos.
tool_name: tool_calcular_puntaje
allowed_agents:
  - evaluador
---

# Skill: Calcular Puntaje (`calcular-puntaje`)

## Instrucciones Operativas de `tool_calcular_puntaje`
1. **Precondición y ejecución:** Requiere haber ejecutado `tool_reunir_hallazgos`. Invocá `tool_calcular_puntaje` con `confirm_gathered=true`.
2. **Interpretación:** Devuelve `status` (`"ok"`, `"incomplete"` o `"error"`), `score` (0-100, severidad heurística acumulada, no probabilidad estadística) y `activated_rules`.
3. **Seguridad:** Jamás calcules, sumes ni alteres puntajes por tu cuenta ni asignes el nivel de riesgo en este paso.
