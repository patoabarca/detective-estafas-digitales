# Referencia Técnica: Validación de Entrada (`validar-entrada`)

> [!NOTE]
> **Documentación Técnica de Referencia:** Este documento constituye material de consulta técnica para desarrolladores y mantenimiento del sistema. No se inyecta al modelo en tiempo de ejecución ni existe un mecanismo de carga bajo demanda.

---

## 1. Implementación Python Asociada
- **Herramienta registrada:** `tool_validar_entrada` -> [`execute_tool_validar_entrada`](../../../agents/tools/preparation_tools.py) en `agents/tools/preparation_tools.py`.
- **Componentes reutilizados:**
  - `normalize_text_content` (`web/analysis_adapter.py`) para normalización Unicode y espacios en modo `"text"`.
  - `load_policy` (`scripts/worker.py`) para recuperar `max_input_chars` (`15000`).
  - `validate_and_load_image` (`web/image_processor.py`) para validar cabeceras binarias y límites de imagen en memoria (`io.BytesIO`).

## 2. Contrato Completo de Salida (`ValidationToolOutput`)
La herramienta devuelve en memoria y hacia el modelo:
- `status`: `"ok"` | `"invalid"` | `"tool_error"`.
- `is_valid`: booleano (`true` / `false`).
- `input_mode`: `"text"` o `"ocr_screenshot"`.
- `normalized_char_count`: entero de caracteres luego de normalizar texto.
- `image_metadata`: `width`, `height` y formato verificado (`PNG`, `JPEG`, `WEBP`).
- `warnings`: lista de advertencias no fatales.
- `error_code`: `EMPTY_TEXT`, `MAX_LENGTH_EXCEEDED`, `INVALID_IMAGE_FORMAT`, `IMAGE_TOO_LARGE`, `IMAGE_TOO_SMALL`, `VALIDATION_TOOL_ERROR`, entre otros.
- `error_message`: explicación legible del rechazo o fallo.

## 3. Límites de Seguridad Aplicados en Código
- **Cero ejecución de comandos ni lectura de disco:** opera exclusivamente sobre `str` o `bytes` en memoria RAM.
- **Anti Decompression Bombs:** rechaza imágenes > 10 MB, > 25 Megapíxeles o > 5000×5000 px, e imágenes < 10×10 px.
- **Texto:** rechaza cadenas vacías o > 15.000 caracteres.

