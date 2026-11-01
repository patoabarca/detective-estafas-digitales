---
name: generar-pdf
description: >-
  Genera el informe descargable en formato PDF en memoria utilizando el motor ReportLab
  existente a partir de la evaluación final validada, sin recalcularla ni modificarla,
  evitando enviar bytes binarios al modelo y protegiendo las rutas contra sobrescrituras.
tool_name: tool_generar_pdf
allowed_agents:
  - evaluador
---

# 📄 Skill: Generar PDF (`generar-pdf`)

## 1. Única Responsabilidad
Representar fielmente la evaluación final validada en un documento PDF estructurado y profesional utilizando el generador existente en `web/pdf_exporter.py` (`generate_pdf_report`). Se ejecuta exclusivamente cuando el usuario solicita la exportación o descarga del informe, operando 100% en memoria (RAM) o escribiendo en la carpeta controlada `output/` con nombres de archivo sanitizados y marcas temporales únicas, sin recalcular ni alterar el resultado de la evaluación.

## 2. Qué Recibe (Entrada)
Recibe a través de la herramienta `tool_generar_pdf`:
- `save_to_output`: parámetro booleano opcional (por defecto `false`). Si es `true`, además de generar el archivo en memoria lo guarda en el directorio local controlado `output/`.
- La herramienta toma los datos ya consolidados de la evaluación (`EvaluationResult` en memoria de sesión) y **no permite que el modelo elija rutas de archivo arbitrarias ni altere el contenido del informe**.

## 3. Qué Devuelve (Salida)
Devuelve un diccionario estructurado y ligero para el modelo con:
- `status`: `"ok"` si el PDF fue generado exitosamente, `"skipped"` si no se solicitó generación de PDF en la llamada actual, o `"error"` ante fallo de formato o biblioteca.
- `pdf_ready`: booleano que confirma que los bytes del PDF están disponibles en la sesión de memoria para descarga inmediata en el navegador.
- `pdf_filename`: nombre de archivo controlado generado automáticamente (por ejemplo, `informe_detective_20261101_143000.pdf`), evitando colisiones o sobrescrituras accidentales.
- `saved_to_disk`: booleano que indica si se guardó una copia en `output/`.
- `byte_size`: tamaño en bytes del documento generado.
- **NUNCA devuelve los bytes binarios crudos del PDF al modelo**, protegiendo el contexto de tokens y la memoria.

## 4. Principios de Integridad y Formato
- **Cero hipervínculos activos a sitios sospechosos:** las URLs sospechosas o maliciosas se imprimen exclusivamente en formato de texto plano no clickeable para evitar accesos accidentales desde el visor de PDF.
- **Escape tipográfico y seguridad:** todo texto del usuario insertado en las plantillas tipográficas se escapa adecuadamente para evitar inyecciones en la sintaxis de marcado de ReportLab.
- **Fidelidad estricta:** los datos de puntaje, nivel, indicadores, reglas activadas y recomendaciones coinciden exactamente con los presentados en la pantalla de la aplicación.
- **Aislamiento de fallos:** un eventual fallo técnico al renderizar o guardar el PDF no invalida ni borra la evaluación del análisis, que permanece visible y utilizable en la interfaz.

## 5. Límites y Seguridad
- No acepta rutas de archivo elegidas por el modelo (prevención de *Path Traversal* y accesos arbitrarios al disco).
- Requiere como precondición obligatoria disponer de una evaluación final en estado `"correcto"` o `"incompleto"` con nivel de riesgo asignado.

