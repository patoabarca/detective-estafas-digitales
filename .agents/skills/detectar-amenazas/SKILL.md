---
name: detectar-amenazas
description: >-
  Detecta amenazas explícitas o implícitas de bloqueo, suspensión, baja de cuenta,
  cierre de servicio, retención de envíos o consecuencias legales/patrimoniales.
tool_name: tool_detectar_amenazas
allowed_agents:
  - analizador_mensajes
---

# ⚠️ Skill: Detectar Amenazas (`detectar-amenazas`)

## 1. Única Responsabilidad
Identificar amenazas de bloqueo, suspensión, cancelación, inhabilitación de cuentas/servicios, retención de paquetes o intimaciones (`ING-AMENAZA-BLOQUEO`) en el texto preparado de la sesión actual, extrayendo los fragmentos exactos que justifican el hallazgo.

## 2. Qué Recibe (Entrada)
Recibe a través de la herramienta `tool_detectar_amenazas` la confirmación de lectura sobre el texto preparado de la sesión (`confirm_session_text: true`).

## 3. Qué Devuelve (Salida)
Devuelve un diccionario estructurado con:
- `status`: `"ok"` o `"tool_error"`.
- `category_reviewed`: `"amenazas"`.
- `detected`: booleano (`true` si se detectaron amenazas, `false` si se revisó sin hallazgos).
- `signals`: lista de señales detectadas (`id: "ING-AMENAZA-BLOQUEO"`, `category: "ingenieria_social"`, `skill_category: "amenazas"`, `severity: "ALTA"`, `description` y `evidence_snippets` sanitizados).
- `warnings`: lista de advertencias si las hubiera.

## 4. Herramienta Python Utilizada
- Función registrada: `tool_detectar_amenazas` en `agents/tools/message_analysis_tools.py`.
- Reutiliza internamente `TextAnalyzer._detect_blocking_threats` de `scripts/analyzer.py`.

## 5. Límites y Manejo de Errores
- **Responsabilidad acotada:** No evalúa urgencia genérica aislada, premios, credenciales ni pagos; no analiza URLs, no hace OCR ni calcula el nivel de riesgo final.
- **Evidencia verificada:** Solo acepta fragmentos presentes en el texto analizado.
- **Manejo de errores:** Ante falta de texto preparado o excepción técnica, devuelve `status: "tool_error"` y detalle del error.
