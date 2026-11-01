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

# 💬 Skill: Explicar Resultado (`explicar-resultado`)

## 1. Única Responsabilidad
Generar la explicación en lenguaje claro, empático y comprensible para usuarios finales sin conocimientos técnicos, utilizando la lógica existente en `ReportGenerator.build_non_technical_explanation`. La redacción se fundamenta de forma estricta en el nivel de riesgo asignado, los indicadores detectados y los análisis de URLs comprobados, preservando el comportamiento existente y evitando cualquier afirmación especulativa sobre contenidos de sitios web que no fueron visitados.

## 2. Qué Recibe (Entrada)
Recibe a través de la herramienta `tool_explicar_resultado`:
- `confirm_level_assigned`: parámetro booleano obligatorio (`true`) que confirma que el nivel de riesgo fue asignado previamente mediante `tool_asignar_nivel_riesgo`.
- La herramienta recupera el nivel de riesgo, los indicadores textuales y el análisis de URLs del estado local validado.

## 3. Qué Devuelve (Salida)
Devuelve un diccionario estructurado con:
- `status`: `"ok"` si la explicación fue construida, o `"error"` si faltó la asignación de nivel previa.
- `risk_level`: nivel de riesgo sobre el que se fundamenta la explicación.
- `explanation`: texto con la explicación no técnica accesible.
- `grounded_indicators`: lista de IDs de señales utilizadas como justificación concreta de la explicación.

## 4. Estructura de la Explicación por Nivel de Riesgo
- **ALTO:** destaca la existencia de peligro inminente, detallando la táctica psicológica identificada (miedo/amenaza de bloqueo para forzar entrega de credenciales, pago anticipado para liberar un premio ficticio, manipulación mediante Prompt Injection o redirección hacia enlaces sospechosos).
- **MEDIO:** explica que se detectaron señales aisladas que llaman la atención (presión temporal o enlaces sin verificar) y aconseja pausar y verificar por canales independientes antes de realizar cualquier acción.
- **BAJO:** comunica con claridad que no se detectaron frases ni patrones típicos de estafas conocidas, recordando de forma pedagógica que la ausencia de señales no es una garantía absoluta de legitimidad y que se debe mantener la cautela cotidiana.
- **INDETERMINADO:** aclara con transparencia que la información provista es insuficiente o fragmentada para emitir un juicio responsable, o que algún análisis especializado quedó incompleto, recomendando no operar sobre enlaces ni datos sensibles.

## 5. Límites y Seguridad
- **Cero alucinaciones:** no agrega hechos, contactos ni detalles no presentes en el mensaje analizado.
- **Cero afirmaciones sobre sitios visitados:** no afirma haber descargado páginas, visto logos ni interactuado con servidores remotos.
- Requiere como precondición que `tool_asignar_nivel_riesgo` haya sido ejecutada previamente.

