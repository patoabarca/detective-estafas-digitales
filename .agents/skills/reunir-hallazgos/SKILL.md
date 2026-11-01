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

# 📦 Skill: Reunir Hallazgos (`reunir-hallazgos`)

## 1. Única Responsabilidad
Reunir de forma estructurada en memoria los resultados validados del Agente Analizador de Mensajes (`MessageAnalysisResult`), del Agente Analizador de Enlaces (`UrlAnalysisResult`, si existían enlaces) y del Agente Preparador (`PreparationResult`). Ejecuta en código Python las dos verificaciones transversales existentes (`SEC-PROMPT-INJECTION` y `SUP-SUPLANTACION-ENTIDAD`) sobre el texto activo mediante `TextAnalyzer.compose_analysis_from_agent_findings`, deduplica indicadores por ID estable conservando evidencia y procedencia, y unifica los análisis de URLs sin perder la evidencia ni la procedencia de cada enlace.

## 2. Qué Recibe (Entrada)
Recibe a través de la herramienta `tool_reunir_hallazgos`:
- `confirm_session`: parámetro booleano obligatorio (`true`) que instruye a la herramienta a recuperar los resultados de la sesión actual validados en memoria local (`session_ctx`).
- **No acepta hallazgos, indicadores ni URLs inventadas o alteradas por el modelo.** Todos los datos provienen del estado local validado.

## 3. Qué Devuelve (Salida)
Devuelve un diccionario estructurado para el modelo con:
- `status`: `"ok"` si los hallazgos de los analistas requeridos fueron unificados satisfactoriamente, `"incomplete"` si faltaron análisis requeridos o quedaron en estado incompleto, o `"error"` ante fallo técnico.
- `total_indicators`: cantidad de indicadores de texto unificados (incluyendo las verificaciones transversales de inyección y suplantación).
- `total_urls_analyzed`: cantidad de URLs analizadas reunidas.
- `indicators_summary`: lista de indicadores unificados (`id`, `categoria`, `severidad`, `descripcion`, `evidence_snippets` sanitizados).
- `url_summary`: lista de análisis de URLs unificados (`url_id`, `masked_url`, `is_ip`, `has_punycode`, `findings`, `reglas_activadas`).
- `warnings`: advertencias acumuladas de la preparación y análisis.

## 4. Deduplicación y Procedencia
- **Indicadores textuales:** si una misma señal fue reportada con múltiples fragmentos, se unifican bajo su identificador canónico (`ING-*`, `FRA-*`, `SEC-*`, `SUP-*`) agregando los fragmentos únicos sin duplicar la señal.
- **Análisis de URLs:** cada URL analizada conserva su identificador (`URL-1`, `URL-2`, etc.), su dominio y sus hallazgos individuales. Una misma regla detectada en distintas URLs (por ejemplo, `REGLA-URL-01` en dos direcciones IP) conserva la evidencia y procedencia de cada enlace sin perder información.

## 5. Límites y Seguridad
- No realiza cálculos de puntaje ni asigna niveles de riesgo (responsabilidad de skills posteriores).
- Prohibido realizar conexiones de red o inspecciones dinámicas.
- Las respuestas enviadas al modelo aplican enmascaramiento preventivo de privacidad sobre fragmentos y URLs.

