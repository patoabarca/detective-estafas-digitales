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

# Skill: Detectar Pedidos de Dinero (`detectar-pedidos-dinero`)

## Instrucciones Operativas de `tool_detectar_pedidos_dinero`
1. **Ejecución:** Invocá `tool_detectar_pedidos_dinero` con `confirm_session_text=true` sobre el texto preparado en sesión para evaluar la categoría `"pedidos_dinero"` (`FRA-PAGO-ANTICIPADO` y `FRA-DEBIN-ENGANOSO`).
2. **Estado y errores:** Devuelve `status="ok"` (`detected=true/false`) o `status="tool_error"` ante fallo técnico o ausencia de texto preparado.
3. **Límites:** Evaluá solo exigencias de pago previo o maniobras DEBIN/transferencia por error; no inventes evidencia literal, no analices URLs ni asignes riesgo final.
