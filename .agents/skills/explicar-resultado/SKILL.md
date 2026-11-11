---
name: explicar-resultado
description: >-
  Genera la explicación accesible, empática y no técnica del resultado de la evaluación
  basada estrictamente en el nivel de riesgo asignado y las evidencias comprobadas,
  sin inventar hechos ni afirmar visitas a sitios externos.
tool_name: tool_explicar_resultado
allowed_agents:
  - evaluador
---

# Skill: Explicar Resultado (`explicar-resultado`)

## Instrucciones Operativas de `tool_explicar_resultado`
1. **Precondición y ejecución:** Requiere `tool_asignar_nivel_riesgo` previo. Invocá `tool_explicar_resultado` con `confirm_level_assigned=true`.
2. **Salida:** Devuelve `status`, `risk_level`, `explanation` y `grounded_indicators` generados determinísticamente en Python.
3. **Límites estrictos:** Basate exclusivamente en las evidencias comprobadas; jamás inventes hechos, contactos ni afirmes haber visitado o descargado sitios web externos.
