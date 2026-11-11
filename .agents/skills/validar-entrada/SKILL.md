---
name: validar-entrada
description: >-
  Valida de forma estricta el tipo, formato, longitud y límites de seguridad de una
  entrada de usuario (texto directo o imagen de captura de pantalla) antes de su
  procesamiento por otros componentes.
tool_name: tool_validar_entrada
allowed_agents:
  - preparador
---

# Skill: Validar Entrada (`validar-entrada`)

## Instrucciones Operativas de `tool_validar_entrada`
1. **Primera herramienta obligatoria:** Invocá `tool_validar_entrada` pasando `input_mode` (`"text"` o `"ocr_screenshot"`) sobre la entrada en memoria de la sesión.
2. **Interpretación de estado:**
   - `status="ok"` (`is_valid=true`): la entrada cumple formato y límites (texto <= 15.000 caracteres; imagen PNG/JPEG/WEBP válida <= 10 MB y <= 25 MP); continuá con la preparación.
   - `status="invalid"` (`is_valid=false`): detené la preparación e informá el motivo (`error_code` / `error_message`).
   - `status="tool_error"`: reportá el fallo técnico sin reintentos ciegos.
3. **Seguridad:** Opera 100% en memoria sin rutas de disco, sin ejecutar comandos ni modificar límites.
