---
name: asignar-nivel-riesgo
description: >-
  Asigna en Python el nivel de riesgo cualitativo (ALTO, MEDIO, BAJO o INDETERMINADO)
  aplicando los umbrales documentados, las combinaciones críticas y los criterios de
  salvaguarda ante análisis incompletos, sin convertir fallos en riesgo bajo.
tool_name: tool_asignar_nivel_riesgo
allowed_agents:
  - evaluador
---

# Skill: Asignar Nivel de Riesgo (`asignar-nivel-riesgo`)

## Instrucciones Operativas de `tool_asignar_nivel_riesgo`
1. **Precondición y ejecución:** Requiere `tool_calcular_puntaje` previo. Invocá `tool_asignar_nivel_riesgo` con `confirm_scored=true`.
2. **Clasificación en Python:** Devuelve `level` (`"ALTO"`, `"MEDIO"`, `"BAJO"` o `"INDETERMINADO"`), `score`, `summary` y `is_critical_combo`.
3. **Regla inviolable de seguridad:** Jamás fijes ni alteres el nivel por tu cuenta; ningún análisis incompleto o con error técnico puede clasificarse como RIESGO BAJO.
