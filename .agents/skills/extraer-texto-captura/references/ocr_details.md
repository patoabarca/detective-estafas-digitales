# Referencia Técnica: Extracción OCR Local (`extraer-texto-captura`)

> [!NOTE]
> **Documentación Técnica de Referencia:** Este documento constituye material de consulta técnica para desarrolladores y mantenimiento del sistema. No se inyecta al modelo en tiempo de ejecución ni existe un mecanismo de carga bajo demanda.

---

## 1. Implementación Python Asociada
- **Herramienta registrada:** `tool_extraer_texto_captura` -> [`execute_tool_extraer_texto_captura`](../../../agents/tools/preparation_tools.py) en `agents/tools/preparation_tools.py`.
- **Componentes reutilizados:**
  - `preprocess_image_for_ocr` (`web/image_processor.py`).
  - `get_ocr_service` (`web/ocr_service.py`) sobre Tesseract OCR (`spa+eng`).

## 2. Contrato Completo de Salida (`OCRToolOutput`)
- `status`: `"ok"` | `"empty_or_illegible"` | `"tool_error"`.
- `extracted_text`: texto reconocido (enmascarado preventivamente hacia el modelo, original conservado en `PreparationSessionContext.raw_active_text`).
- `char_count`: longitud en caracteres del texto reconocido.
- `language_used`: idioma utilizado por Tesseract (ej. `"spa+eng"`).
- `ocr_url_warnings`: advertencias de posibles distorsiones OCR sobre enlaces (espacios en protocolos, comas por puntos, `'vv'` por `'w'`, números por letras).
- `error_message`: detalle técnico cuando `status` es `"tool_error"` o `"empty_or_illegible"`.

## 3. Reglas de Privacidad y Fallo
- La imagen se procesa localmente en RAM y nunca se envía a APIs externas.
- `"empty_or_illegible"` deriva en `PreparationResult(estado="incompleto", detalle_estado="texto_no_extraible")`.
- `"tool_error"` deriva en `PreparationResult(estado="error", detalle_estado="fallo_herramienta")`.

