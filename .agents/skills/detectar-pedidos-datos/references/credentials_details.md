# Referencia Técnica: Detectar Pedidos de Datos Sensibles (`detectar-pedidos-datos`)

> [!NOTE]
> **Documentación Técnica de Referencia:** Este documento constituye material de consulta técnica para desarrolladores y mantenimiento del sistema. No se inyecta al modelo en tiempo de ejecución ni existe un mecanismo de carga bajo demanda.

## 1. Implementación Python Asociada
- **Herramienta registrada:** `tool_detectar_pedidos_datos` en `agents/tools/message_analysis_tools.py`.
- **Detector subyacente:** `TextAnalyzer._detect_credential_harvesting` en `scripts/analyzer.py` (incluye salvaguardas frente a advertencias educativas como *"Nunca compartas tu clave"*).
- **Regla / Señal:** `FRA-CAPTURA-CREDENCIALES` (`categoria`: `"captura_datos"`, `skill_category`: `"pedidos_datos"`, `severity`: `"ALTA"`).

## 2. Estructura Completa de Salida
- `status`: `"ok"` o `"tool_error"`.
- `category_reviewed`: `"pedidos_datos"`.
- `detected`: booleano.
- `signals`: lista de señales con `id`, `category`, `skill_category`, `severity`, `description` y `evidence_snippets` sanitizados.
- `warnings`: advertencias no fatales acumuladas.
