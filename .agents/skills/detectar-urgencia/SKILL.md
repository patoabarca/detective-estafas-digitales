---
name: detectar-urgencia
description: >-
  Detecta expresiones de presión temporal, plazos perentorios o urgencia artificial
  diseñados para forzar decisiones apresuradas en mensajes potencialmente fraudulentos.
tool_name: tool_detectar_urgencia
allowed_agents:
  - analizador_mensajes
---

# ⏱️ Skill: Detectar Urgencia (`detectar-urgencia`)

## 1. Única Responsabilidad
Identificar indicadores lingüísticos de urgencia artificial, presión temporal o plazos límite (`ING-URGENCIA-ARTIFICIAL`) en el texto preparado de la sesión actual, extrayendo los fragmentos exactos que justifican el hallazgo.

## 2. Qué Recibe (Entrada)
Recibe a través de la herramienta `tool_detectar_urgencia` la referencia al texto preparado de la sesión actual (`confirm_session_text: true`). La herramienta opera en memoria sobre el texto preparado local sin aceptar textos arbitrarios ni rutas de archivos externas.

## 3. Qué Devuelve (Salida)
Devuelve un diccionario estructurado con:
- `status`: `"ok"` o `"tool_error"`.
- `category_reviewed`: `"urgencia"`.
- `detected`: booleano (`true` si se detectó urgencia artificial, `false` si la categoría fue revisada sin hallazgos).
- `signals`: lista de señales detectadas (con `id: "ING-URGENCIA-ARTIFICIAL"`, `category: "ingenieria_social"`, `skill_category: "urgencia"`, `severity: "MEDIA"`, `description` y `evidence_snippets` sanitizados para el retorno al modelo).
- `warnings`: lista de advertencias si las hubiera.

## 4. Herramienta Python Utilizada
- Función registrada: `tool_detectar_urgencia` en `agents/tools/message_analysis_tools.py`.
- Reutiliza internamente `TextAnalyzer._detect_urgency` de `scripts/analyzer.py`.

## 5. Límites y Manejo de Errores
- **Responsabilidad acotada:** No evalúa amenazas de bloqueo, premios, pedidos de credenciales ni pedidos de dinero; no analiza URLs, no ejecuta OCR ni asigna puntaje de riesgo final.
- **Evidencia verificada:** Solo devuelve fragmentos que existen literalmente en el texto preparado.
- **Manejo de errores:** Si no hay texto preparado válido en la sesión o ocurre un fallo interno, devuelve `status: "tool_error"` con `error_message` explícito para que el agente reporte el análisis como `"error"`.

