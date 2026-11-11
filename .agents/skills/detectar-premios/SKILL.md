---
name: detectar-premios
description: >-
  Detecta promesas de premios inesperados, sorteos no verificables, órdenes de compra
  o beneficios extraordinarios utilizados como señuelo de ingeniería social.
tool_name: tool_detectar_premios
allowed_agents:
  - analizador_mensajes
---

# Skill: Detectar Premios (`detectar-premios`)

## Instrucciones Operativas de `tool_detectar_premios`
1. **Ejecución:** Invocá `tool_detectar_premios` con `confirm_session_text=true` sobre el texto preparado en sesión para evaluar la categoría `"premios"` (`FRA-PREMIO-INESPERADO`).
2. **Estado y errores:** Devuelve `status="ok"` (`detected=true/false`) o `status="tool_error"` ante falta de texto o error técnico.
3. **Límites:** Evaluá solo señuelos de premios/sorteos (no pedidos de dinero anticipado, que corresponden a `detectar-pedidos-dinero`); no inventes evidencia ni asignes riesgo final.
