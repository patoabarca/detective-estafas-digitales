# Referencia Técnica: Calcular Puntaje (`calcular-puntaje`)

> [!NOTE]
> **Documentación Técnica de Referencia:** Este documento constituye material de consulta técnica para desarrolladores y mantenimiento del sistema. No se inyecta al modelo en tiempo de ejecución ni existe un mecanismo de carga bajo demanda.

## 1. Implementación Python Asociada
- **Herramienta registrada:** `tool_calcular_puntaje` en `agents/tools/evaluation_tools.py`.
- **Motor utilizado:** `RiskClassifier.calculate_score` en `scripts/risk_classifier.py` apoyado en `config/policy.json` y `classify_url_risk_signals` (`scripts/url_analyzer.py`).

## 2. Reglas Ponderadas Reutilizadas (`policy.json`)
- **Seguridad IA:** `REGLA-SEC-01` (+45 pts) por Prompt Injection.
- **Fraude Financiero:** `REGLA-FRA-01` (+40 pts) captura de claves/OTP; `REGLA-FRA-02` (+35 pts) pago anticipado; `REGLA-FRA-03` (+25 pts) premio inesperado; `REGLA-FRA-04` (+30 pts) maniobra DEBIN.
- **Ingeniería Social:** `REGLA-ING-01` (+35 pts) amenaza de bloqueo/suspensión; `REGLA-ING-02` (+15 pts) urgencia/presión temporal; `REGLA-SUP-01` (+15 pts) invocación de entidad en contexto coercitivo.
- **URLs Sospechosas:** `REGLA-URL-01` (+30 pts) IP numérica; `REGLA-URL-02` (+30 pts) subdominio engañoso; `REGLA-URL-03` (+25 pts) Punycode/homóglifos; `REGLA-URL-04` (+20 pts) credenciales embebidas; `REGLA-URL-05` (+20 pts) TLD de bajo costo (sin concurrencia con `REGLA-URL-02`).
- Tope estricto: `min(score, 100)`.

## 3. Salida Completa
- `status` (`"ok"` | `"incomplete"` | `"error"`), `score` (0-100), `activated_rules`, `is_indeterminate`, `summary`.
