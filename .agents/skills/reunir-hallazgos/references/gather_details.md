# Referencia Técnica: Reunir Hallazgos (`reunir-hallazgos`)

> [!NOTE]
> **Documentación Técnica de Referencia:** Este documento constituye material de consulta técnica para desarrolladores y mantenimiento del sistema. No se inyecta al modelo en tiempo de ejecución ni existe un mecanismo de carga bajo demanda.

## 1. Implementación Python Asociada
- **Herramienta registrada:** `tool_reunir_hallazgos` en `agents/tools/evaluation_tools.py`.
- **Composición transversal:** Ejecuta `TextAnalyzer.compose_analysis_from_agent_findings` (`scripts/analyzer.py`), incorporando únicamente las verificaciones transversales `SEC-PROMPT-INJECTION` y `SUP-SUPLANTACION-ENTIDAD` sin reejecutar los detectores de categorías ya evaluadas.

## 2. Deduplicación y Procedencia
- **Indicadores textuales:** Se unifican bajo ID estable (`ING-*`, `FRA-*`, `SEC-*`, `SUP-*`) combinando fragmentos únicos sin duplicar la señal.
- **Análisis de URLs:** Cada enlace conserva su identificador (`URL-1`, `URL-2`, ...), dominio, hallazgos y reglas activadas sin perder procedencia.

## 3. Estructura Completa de Salida
- `status`: `"ok"` | `"incomplete"` | `"error"`.
- `total_indicators`, `total_urls_analyzed`, `indicators_summary`, `url_summary`, `warnings`.
