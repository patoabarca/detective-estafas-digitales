---
name: recomendar-cuidados
description: >-
  Selecciona las recomendaciones preventivas del sistema adecuadas según el nivel
  de riesgo determinado y la presencia de enlaces o pedidos de credenciales, sin inventar
  contactos, números telefónicos ni instituciones no mencionadas.
tool_name: tool_recomendar_cuidados
allowed_agents:
  - evaluador
---

# Skill: Recomendar Cuidados (`recomendar-cuidados`)

## Instrucciones Operativas de `tool_recomendar_cuidados`
1. **Precondición y ejecución:** Requiere `tool_asignar_nivel_riesgo` previo. Invocá `tool_recomendar_cuidados` con `confirm_level_assigned=true`.
2. **Salida:** Devuelve `recommendations` seleccionadas por el sistema según nivel de riesgo y presencia de URLs o pedidos de claves/dinero.
3. **Límites estrictos:** Presentalas como recomendaciones preventivas del sistema; jamás inventes números telefónicos, correos, alias ni instituciones no mencionadas en el mensaje.
