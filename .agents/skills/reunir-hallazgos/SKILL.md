---
name: reunir-hallazgos
description: >-
  Reúne, unifica y deduplica los hallazgos validados de ambos analistas especializados
  (mensaje y enlaces) y las advertencias del preparador en la sesión actual, conservando
  la procedencia y evidencia de cada indicador y enlace sin alterar los textos analizados.
tool_name: tool_reunir_hallazgos
allowed_agents:
  - evaluador
---

# Skill: Reunir Hallazgos (`reunir-hallazgos`)

## Instrucciones Operativas de `tool_reunir_hallazgos`
1. **Ejecución:** Invocá `tool_reunir_hallazgos` con `confirm_session=true` como primer paso de la evaluación para unificar en memoria los resultados validados de preparación, análisis de mensaje y enlaces.
2. **Estado:** Devuelve `status="ok"`, `"incomplete"` (si faltó algún análisis requerido) o `"error"`.
3. **Seguridad:** No acepta hallazgos ni URLs propuestos por el modelo, no realiza cálculos de puntaje/riesgo ni conexiones de red, y aplica enmascaramiento preventivo de PII en la salida.
