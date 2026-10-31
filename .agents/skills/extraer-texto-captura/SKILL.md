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

# 📷 Skill: Extraer Texto de Captura (`extraer-texto-captura`)

## 1. Única Responsabilidad
Ejecutar el reconocimiento óptico de caracteres (OCR) local sobre la imagen validada en la sesión actual, sanear el texto extraído y detectar anomalías tipográficas típicas del OCR sobre posibles URLs, sin enviar la imagen a servicios externos ni inventar contenido cuando la imagen sea ilegible.

## 2. Qué Recibe (Entrada)
Recibe mediante la herramienta `tool_extraer_texto_captura` la orden de procesar la imagen ya validada en el contexto seguro de la sesión actual (sin aceptar rutas arbitrarias del sistema de archivos).

## 3. Qué Devuelve (Salida)
Devuelve un diccionario estructurado (`OCRToolOutput`) con:
- `status`:
  - `"ok"`: se extrajo texto legible de la captura.
  - `"empty_or_illegible"`: el motor OCR funcionó pero la captura no contiene texto legible o está en blanco.
  - `"tool_error"`: Tesseract OCR no está disponible en el entorno o falló durante el procesamiento.
- `extracted_text`: cadena de texto extraída (con datos sensibles enmascarados para el contexto del agente, preservando el original en memoria local). Vacía (`""`) si no se pudo extraer texto.
- `char_count`: longitud del texto extraído.
- `language_used`: idioma empleado por Tesseract (ej. `"spa+eng"`).
- `ocr_url_warnings`: lista de advertencias sobre posibles distorsiones del OCR en enlaces (espacios en protocolos, comas por puntos, `'vv'` por `'w'`, números por letras).
- `error_message`: detalle técnico claro cuando `status` es `"tool_error"` o `"empty_or_illegible"`.

## 4. Herramienta Python Utilizada
- Función registrada: `tool_extraer_texto_captura` en `agents/tools/preparation_tools.py`.
- Reutiliza internamente `preprocess_image_for_ocr` (`web/image_processor.py`) y `get_ocr_service` (`web/ocr_service.py`).

## 5. Límites y Manejo de Errores
- **Cero invención de texto:** si la captura es borrosa, ilegible o no tiene texto, devuelve `status: "empty_or_illegible"` y `extracted_text: ""`. El agente **jamás** debe inventar o suponer el texto de la captura.
- **Procesamiento 100% local:** la imagen jamás se envía a la API del LLM; se procesa localmente con Tesseract en memoria RAM.
- **Diferenciación de fallos:** distingue explícitamente entre captura sin texto legible (`"empty_or_illegible"` -> estado de preparación `"incompleto"`) y fallo técnico del binario OCR (`"tool_error"` -> estado de preparación `"error"`).
