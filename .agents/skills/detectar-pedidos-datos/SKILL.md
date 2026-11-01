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

# 🔐 Skill: Detectar Pedidos de Datos Sensibles (`detectar-pedidos-datos`)

## 1. Única Responsabilidad
Identificar solicitudes directas o indirectas de datos sensibles, claves, códigos de verificación (OTP/SMS), tokens o formularios de validación de identidad (`FRA-CAPTURA-CREDENCIALES`) en el texto preparado de la sesión actual, excluyendo advertencias educativas legítimas (por ejemplo, *"Nunca compartas tu clave"*).

## 2. Qué Recibe (Entrada)
Recibe a través de la herramienta `tool_detectar_pedidos_datos` la confirmación para analizar el texto preparado de la sesión (`confirm_session_text: true`).

## 3. Qué Devuelve (Salida)
Devuelve un diccionario estructurado con:
- `status`: `"ok"` o `"tool_error"`.
- `category_reviewed`: `"pedidos_datos"`.
- `detected`: booleano (`true` si se detectó pedido de datos sensibles, `false` si se revisó sin hallazgos).
- `signals`: lista de señales detectadas (`id: "FRA-CAPTURA-CREDENCIALES"`, `category: "captura_datos"`, `skill_category: "pedidos_datos"`, `severity: "ALTA"`, `description` y `evidence_snippets` sanitizados).
- `warnings`: lista de advertencias si las hubiera.

## 4. Herramienta Python Utilizada
- Función registrada: `tool_detectar_pedidos_datos` en `agents/tools/message_analysis_tools.py`.
- Reutiliza internamente `TextAnalyzer._detect_credential_harvesting` de `scripts/analyzer.py`.

## 5. Límites y Manejo de Errores
- **Responsabilidad acotada:** No evalúa transferencias de dinero ni DEBIN, no analiza URLs, no realiza OCR ni calcula el puntaje de riesgo final.
- **Evidencia verificada y privacidad:** Verifica que los fragmentos existan en el texto preparado y aplica enmascaramiento preventivo antes de devolverlos al modelo externo.
- **Manejo de errores:** Informa cualquier fallo técnico mediante `status: "tool_error"`.

