# Referencia Técnica: Explicar Resultado (`explicar-resultado`)

> [!NOTE]
> **Documentación Técnica de Referencia:** Este documento constituye material de consulta técnica para desarrolladores y mantenimiento del sistema. No se inyecta al modelo en tiempo de ejecución ni existe un mecanismo de carga bajo demanda.

## 1. Implementación Python Asociada
- **Herramienta registrada:** `tool_explicar_resultado` en `agents/tools/evaluation_tools.py`.
- **Generador reutilizado:** `ReportGenerator.build_non_technical_explanation` en `scripts/report_generator.py`.

## 2. Estructura de Explicación por Nivel
- **ALTO:** Explica la táctica psicológica y señales comprobadas (coerción/amenaza, solicitud de credenciales, pago anticipado, prompt injection o URL sospechosa).
- **MEDIO:** Señala indicadores aislados y sugiere verificar por canales oficiales.
- **BAJO:** Reconoce cualquier señal aislada presente o aclara ausencia de patrones conocidos sin garantizar legitimidad absoluta.
- **INDETERMINADO:** Transparenta contenido insuficiente o análisis incompleto.

## 3. Salida Completa
- `status`, `risk_level`, `explanation`, `grounded_indicators`.
