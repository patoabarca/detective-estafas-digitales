# Referencia Técnica: Detectar Amenazas (`detectar-amenazas`)

> [!NOTE]
> **Documentación Técnica de Referencia:** Este documento constituye material de consulta técnica para desarrolladores y mantenimiento del sistema. No se inyecta al modelo en tiempo de ejecución ni existe un mecanismo de carga bajo demanda.

## 1. Implementación Python Asociada
- **Herramienta registrada:** `tool_detectar_amenazas` en `agents/tools/message_analysis_tools.py`.
- **Detector subyacente:** `TextAnalyzer._detect_blocking_threats` en `scripts/analyzer.py`.
- **Regla / Señal:** `ING-AMENAZA-BLOQUEO` (`categoria`: `"ingenieria_social"`, `skill_category`: `"amenazas"`, `severity`: `"ALTA"`).

## 2. Estructura Completa de Salida
- `status`: `"ok"` o `"tool_error"`.
- `category_reviewed`: `"amenazas"`.
- `detected`: booleano.
- `signals`: lista de señales con `id`, `category`, `skill_category`, `severity`, `description` y `evidence_snippets` sanitizados.
- `warnings`: advertencias no fatales acumuladas.
