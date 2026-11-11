---
name: extraer-texto-captura
description: >-
  Extrae el texto contenido en una imagen o captura de pantalla previamente validada
  utilizando reconocimiento óptico de caracteres (Tesseract OCR) 100% local en memoria,
  detectando posibles distorsiones tipográficas en direcciones web.
tool_name: tool_extraer_texto_captura
allowed_agents:
  - preparador
---

# Skill: Extraer Texto de Captura (`extraer-texto-captura`)

## Instrucciones Operativas de `tool_extraer_texto_captura`
1. **Precondición:** Invocala únicamente en modo `"ocr_screenshot"` después de que `tool_validar_entrada` devuelva `status="ok"`. Acepta opcionalmente `preprocess` (booleano).
2. **Interpretación de estado:**
   - `status="ok"`: se extrajo texto legible; continuá invocando `tool_extraer_enlaces`.
   - `status="empty_or_illegible"`: la imagen no contiene texto legible; **NO** invoques `tool_extraer_enlaces` y finalizá informando el estado incompleto.
   - `status="tool_error"`: fallo del motor OCR local; finalizá informando el error técnico.
3. **Reglas estrictas:**
   - **Cero invención ni autocorrección:** jamás inventes texto si la captura es ilegible ni corrijas URLs con advertencias OCR (`ocr_url_warnings`).
   - **Procesamiento local:** la imagen se procesa 100% en memoria RAM sin enviarse a servicios externos.
