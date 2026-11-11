# Referencia Técnica: Detectar Pedidos de Dinero (`detectar-pedidos-dinero`)

> [!NOTE]
> **Documentación Técnica de Referencia:** Este documento constituye material de consulta técnica para desarrolladores y mantenimiento del sistema. No se inyecta al modelo en tiempo de ejecución ni existe un mecanismo de carga bajo demanda.

## 1. Implementación Python Asociada
- **Herramienta registrada:** `tool_detectar_pedidos_dinero` en `agents/tools/message_analysis_tools.py`.
- **Detectores subyacentes:** `TextAnalyzer._detect_advance_fee` y `TextAnalyzer._detect_debin_trick` en `scripts/analyzer.py`.
- **Reglas / Señales:** `FRA-PAGO-ANTICIPADO` y `FRA-DEBIN-ENGANOSO` (`categoria`: `"fraude_financiero"`, `skill_category`: `"pedidos_dinero"`, `severity`: `"ALTA"`).

## 2. Estructura Completa de Salida
- `status`: `"ok"` o `"tool_error"`.
- `category_reviewed`: `"pedidos_dinero"`.
- `detected`: booleano.
- `signals`: lista de señales con `id`, `category`, `skill_category`, `severity`, `description` y `evidence_snippets` sanitizados.
- `warnings`: advertencias no fatales acumuladas.
