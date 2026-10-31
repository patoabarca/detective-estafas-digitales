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

# 🛡️ Skill: Validar Entrada (`validar-entrada`)

## 1. Única Responsabilidad
Verificar que la entrada suministrada por el usuario (texto plano o bytes de una captura de pantalla en memoria) cumpla con los controles estructurales, de tamaño, extensión, cabecera binaria y resolución antes de continuar con el flujo de preparación.

## 2. Qué Recibe (Entrada)
Recibe a través de la herramienta `tool_validar_entrada` el identificador de contexto en memoria (`input_mode`: `"text"` o `"ocr_screenshot"`) junto con el contenido pre-cargado en el contexto de ejecución seguro:
- Si `input_mode == "text"`: cadena de texto y longitud máxima permitida (`max_chars = 15000`).
- Si `input_mode == "ocr_screenshot"`: flujo de bytes en memoria (`file_bytes`) y nombre de archivo orientativo (`filename`).

## 3. Qué Devuelve (Salida)
Devuelve un diccionario estructurado (`ValidationToolOutput`) con:
- `status`: `"ok"` si la entrada es válida, `"invalid"` si viola una regla de validación, o `"tool_error"` si ocurrió un fallo inesperado.
- `is_valid`: booleano (`true` / `false`).
- `input_mode`: `"text"` o `"ocr_screenshot"`.
- `normalized_char_count`: cantidad de caracteres luego de normalizar espacios y Unicode (en modo texto).
- `image_metadata`: resolución (`width`, `height`) y formato real verificado (`PNG`, `JPEG`, `WEBP`) cuando es imagen.
- `warnings`: lista de advertencias no fatales.
- `error_code`: código estandarizado en caso de rechazo (`EMPTY_TEXT`, `MAX_LENGTH_EXCEEDED`, `INVALID_IMAGE_FORMAT`, `IMAGE_TOO_LARGE`, `IMAGE_TOO_SMALL`, etc.).
- `error_message`: explicación clara del motivo de invalidez.

## 4. Herramienta Python Utilizada
- Función registrada: `tool_validar_entrada` en `agents/tools/preparation_tools.py`.
- Reutiliza internamente `normalize_text_content` (`web/analysis_adapter.py`), `load_policy` (`scripts/worker.py`) y `validate_and_load_image` (`web/image_processor.py`).

## 5. Límites y Manejo de Errores
- **Cero ejecución de comandos ni acceso a disco:** valida exclusivamente datos en memoria (`io.BytesIO` / `str`).
- **Prevención de Decompression Bombs:** rechaza imágenes mayores a 10 MB, 25 Megapíxeles o 5000x5000 px, e imágenes menores a 10x10 px.
- **Límite de texto:** rechaza textos vacíos (solo espacios) o que superen los 15.000 caracteres.
- **Reporte de errores:** nunca lanza excepciones no controladas al agente; devuelve `is_valid: false` con `status: "invalid"` y el `error_code` específico para que el Agente Preparador reporte el estado `"error"` (entrada no válida).
