# Referencia Técnica: Recomendar Cuidados (`recomendar-cuidados`)

> [!NOTE]
> **Documentación Técnica de Referencia:** Este documento constituye material de consulta técnica para desarrolladores y mantenimiento del sistema. No se inyecta al modelo en tiempo de ejecución ni existe un mecanismo de carga bajo demanda.

## 1. Implementación Python Asociada
- **Herramienta registrada:** `tool_recomendar_cuidados` en `agents/tools/evaluation_tools.py`.
- **Generador reutilizado:** `ReportGenerator.get_recommendations` en `scripts/report_generator.py`.

## 2. Catálogo de Recomendaciones Preventivas del Sistema
- **ALTO / MEDIO:** No abrir enlaces (si hay URLs), no compartir contraseñas/tokens/PIN/OTP (si hay captura de datos), no responder, verificar por canales públicos oficiales y cambiar claves desde otro dispositivo ante sospecha de exposición.
- **INDETERMINADO:** Información insuficiente; evitar compartir datos hasta verificar remitente.
- **BAJO:** Mantener precaución cotidiana y recordar que bancos/organismos no piden claves por mensaje directo.

## 3. Salida Completa
- `status`, `recommendations_count`, `recommendations`, `context_flags` (`has_urls`, `has_credentials`, `risk_level`).
