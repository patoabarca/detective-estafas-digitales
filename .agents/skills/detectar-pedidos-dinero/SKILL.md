---
name: detectar-pedidos-dinero
description: >-
  Detecta exigencias de pagos anticipados (tasas de envío, aduana, seguros postales,
  gastos administrativos) y maniobras de extracción de fondos mediante DEBIN o
  supuestas transferencias por error.
tool_name: tool_detectar_pedidos_dinero
allowed_agents:
  - analizador_mensajes
---

# 💸 Skill: Detectar Pedidos de Dinero (`detectar-pedidos-dinero`)

## 1. Única Responsabilidad
Identificar solicitudes de dinero o transferencias fraudulentas en el texto preparado de la sesión actual, abarcando las dos reglas financieras del motor:
1. Pago anticipado de aranceles, fletes, tasas o seguros para liberar premios/envíos (`FRA-PAGO-ANTICIPADO`).
2. Maniobras de débito inmediato (`DEBIN`) o supuestas transferencias realizadas por error (`FRA-DEBIN-ENGANOSO`).

## 2. Qué Recibe (Entrada)
Recibe a través de la herramienta `tool_detectar_pedidos_dinero` la confirmación para inspeccionar el texto preparado de la sesión (`confirm_session_text: true`).

## 3. Qué Devuelve (Salida)
Devuelve un diccionario estructurado con:
- `status`: `"ok"` o `"tool_error"`.
- `category_reviewed`: `"pedidos_dinero"`.
- `detected`: booleano (`true` si se detectó alguna de las señales de pedido de dinero, `false` si se revisó sin hallazgos).
- `signals`: lista de señales detectadas (`FRA-PAGO-ANTICIPADO` y/o `FRA-DEBIN-ENGANOSO`, con `category: "fraude_financiero"`, `skill_category: "pedidos_dinero"`, `severity: "ALTA"`, `description` y `evidence_snippets` sanitizados).
- `warnings`: lista de advertencias si las hubiera.

## 4. Herramienta Python Utilizada
- Función registrada: `tool_detectar_pedidos_dinero` en `agents/tools/message_analysis_tools.py`.
- Reutiliza internamente `TextAnalyzer._detect_advance_fee` y `TextAnalyzer._detect_debin_trick` de `scripts/analyzer.py`.

## 5. Límites y Manejo de Errores
- **Responsabilidad acotada:** No evalúa la promesa del premio en sí (`detectar-premios`), ni amenazas, urgencia o credenciales; no analiza URLs, no hace OCR ni calcula el riesgo final.
- **Evidencia verificada:** Comprueba que todo fragmento reportado exista exactamente en el texto preparado.
- **Manejo de errores:** Devuelve `status: "tool_error"` si no hay texto preparado en la sesión o si ocurre una excepción.
