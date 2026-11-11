---
name: detectar-pedidos-datos
description: >-
  Detecta solicitudes de credenciales, contraseñas, tokens, códigos OTP/SMS, PIN,
  datos de tarjetas o validaciones de identidad/titularidad, respetando salvaguardas
  de contexto educativo o preventivo.
tool_name: tool_detectar_pedidos_datos
allowed_agents:
  - analizador_mensajes
---

# Skill: Detectar Pedidos de Datos Sensibles (`detectar-pedidos-datos`)

## Instrucciones Operativas de `tool_detectar_pedidos_datos`
1. **Ejecución:** Invocá `tool_detectar_pedidos_datos` con `confirm_session_text=true` sobre el texto preparado en sesión para evaluar la categoría `"pedidos_datos"` (`FRA-CAPTURA-CREDENCIALES`).
2. **Estado y errores:** Devuelve `status="ok"` (`detected=true/false`) o `status="tool_error"` si falla la herramienta.
3. **Límites y privacidad:** Evaluá solo solicitudes de claves, tokens, OTP/SMS, PIN o validación de identidad (respetando advertencias preventivas legítimas); devolvé evidencia literal sanitizada, sin analizar URLs ni asignar riesgo final.
