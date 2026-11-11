# Referencia Técnica: Generar PDF (`generar-pdf`)

> [!NOTE]
> **Documentación Técnica de Referencia:** Este documento constituye material de consulta técnica para desarrolladores y mantenimiento del sistema. No se inyecta al modelo en tiempo de ejecución ni existe un mecanismo de carga bajo demanda.

## 1. Implementación Python Asociada
- **Herramienta registrada:** `tool_generar_pdf` en `agents/tools/evaluation_tools.py`.
- **Exportador utilizado:** `generate_pdf_report` en `web/pdf_exporter.py` (ReportLab en `io.BytesIO`).

## 2. Principios de Seguridad y Formato
- Cero hipervínculos activos a URLs sospechosas (texto plano no clickeable).
- Escape tipográfico seguro para marcado XML de ReportLab.
- Nombres de archivo controlados automáticamente en `./output/` (sin aceptar rutas arbitrarias para evitar *Path Traversal*).
- Un fallo en la generación de PDF no borra ni invalida la evaluación en memoria.

## 3. Salida Completa
- `status` (`"ok"` | `"skipped"` | `"error"`), `pdf_ready`, `pdf_filename`, `saved_to_disk`, `byte_size`.
