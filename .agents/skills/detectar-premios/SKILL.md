---
name: detectar-premios
description: >-
  Detecta promesas de premios inesperados, sorteos no verificables, órdenes de compra
  o beneficios extraordinarios utilizados como señuelo de ingeniería social.
tool_name: tool_detectar_premios
allowed_agents:
  - analizador_mensajes
---

# 🎁 Skill: Detectar Premios (`detectar-premios`)

## 1. Única Responsabilidad
Identificar promesas de premios, sorteos, regalos o beneficios extraordinarios usados como señuelo (`FRA-PREMIO-INESPERADO`) en el texto preparado de la sesión actual, devolviendo los fragmentos textuales que lo respaldan.

## 2. Qué Recibe (Entrada)
Recibe a través de la herramienta `tool_detectar_premios` la referencia al texto preparado de la sesión (`confirm_session_text: true`).

## 3. Qué Devuelve (Salida)
Devuelve un diccionario estructurado con:
- `status`: `"ok"` o `"tool_error"`.
- `category_reviewed`: `"premios"`.
- `detected`: booleano (`true` si se detectó señuelo de premio/beneficio, `false` si se revisó sin hallazgos).
- `signals`: lista de señales detectadas (`id: "FRA-PREMIO-INESPERADO"`, `category: "fraude_financiero"`, `skill_category: "premios"`, `severity: "ALTA"`, `description` y `evidence_snippets` sanitizados).
- `warnings`: lista de advertencias si las hubiera.

## 4. Herramienta Python Utilizada
- Función registrada: `tool_detectar_premios` en `agents/tools/message_analysis_tools.py`.
- Reutiliza internamente `TextAnalyzer._detect_fake_rewards` de `scripts/analyzer.py`.

## 5. Límites y Manejo de Errores
- **Responsabilidad acotada:** No evalúa el pedido posterior de dinero (`FRA-PAGO-ANTICIPADO`, que corresponde a `detectar-pedidos-dinero`), ni urgencia, amenazas o credenciales; no analiza URLs ni asigna riesgo global.
- **Evidencia verificada:** Todo fragmento devuelto debe pertenecer literalmente al texto preparado.
- **Manejo de errores:** Si falla la ejecución o no existe texto preparado, devuelve `status: "tool_error"`.
