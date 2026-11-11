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

# Skill: Generar PDF (`generar-pdf`)

## Instrucciones Operativas de `tool_generar_pdf`
1. **Uso condicional:** Ejecutala únicamente cuando el usuario haya solicitado generar el PDF (`save_to_output=true` solo si pidió guardarlo en `./output`). Requiere una evaluación final asignada.
2. **Salida:** Devuelve `status` (`"ok"`, `"skipped"` o `"error"`), `pdf_ready`, `pdf_filename` y `byte_size`.
3. **Seguridad:** Opera en memoria sobre la evaluación validada; nunca devuelve bytes binarios crudos al modelo, nunca recalcula puntajes y no acepta rutas arbitrarias de archivo.
