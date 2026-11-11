# Referencia Técnica: Extracción Estática de Enlaces (`extraer-enlaces`)

> [!NOTE]
> **Documentación Técnica de Referencia:** Este documento constituye material de consulta técnica para desarrolladores y mantenimiento del sistema. No se inyecta al modelo en tiempo de ejecución ni existe un mecanismo de carga bajo demanda.

---

## 1. Implementación Python Asociada
- **Herramienta registrada:** `tool_extraer_enlaces` -> [`execute_tool_extraer_enlaces`](../../../agents/tools/preparation_tools.py) en `agents/tools/preparation_tools.py`.
- **Componentes reutilizados:**
  - `extract_urls` (`scripts/url_analyzer.py`) — solo extracción sintáctica, sin invocar `analyze_single_url`.
  - `build_session_url_maps` (`agents/common/privacy.py`) vía `PreparationSessionContext.ensure_url_maps()` para asignar `URL-1`, `URL-2`, ... y sus versiones sanitizadas.

## 2. Contrato Completo de Salida
- `status`: `"ok"` (si `links_count > 0`), `"no_links"` (si `links_count == 0`), o `"tool_error"`.
- `links_count`: cantidad entera de URLs únicas extraídas.
- `url_ids`: identificadores estables asignados (`["URL-1", ...]`).
- `urls`: vista sanitizada de los enlaces para el modelo.
- `warnings`: advertencias acumuladas (incluyendo `ocr_url_warnings`).
- `error_message`: `null` o descripción técnica del fallo.

