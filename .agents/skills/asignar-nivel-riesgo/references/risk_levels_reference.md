# Referencia Técnica: Asignar Nivel de Riesgo (`asignar-nivel-riesgo`)

> [!NOTE]
> **Documentación Técnica de Referencia:** Este documento constituye material de consulta técnica para desarrolladores y mantenimiento del sistema. No se inyecta al modelo en tiempo de ejecución ni existe un mecanismo de carga bajo demanda.

## 1. Implementación Python Asociada
- **Herramienta registrada:** `tool_asignar_nivel_riesgo` en `agents/tools/evaluation_tools.py`.
- **Motor utilizado:** `RiskClassifier.assign_risk_level` en `scripts/risk_classifier.py`.

## 2. Criterios de Clasificación (`policy.json`)
- **ALTO:** puntaje `>= 50`, `SEC-PROMPT-INJECTION`, o combinaciones críticas (`ING-AMENAZA-BLOQUEO` + `FRA-CAPTURA-CREDENCIALES`/URL sospechosa; `FRA-CAPTURA-CREDENCIALES` + URL sospechosa; (`ING-AMENAZA-BLOQUEO` o `ING-URGENCIA-ARTIFICIAL`) + `FRA-CAPTURA-CREDENCIALES`; `FRA-PAGO-ANTICIPADO`; `FRA-DEBIN-ENGANOSO`).
- **MEDIO:** puntaje `>= 20` y `< 50` sin combinación crítica.
- **BAJO:** puntaje `< 20` sin combinaciones críticas ni etapas incompletas.
- **INDETERMINADO:** texto insuficiente (< 15 chars o CTA aislado < 45 chars sin evidencia), `MessageAnalysisResult.estado == "incompleto"` o `UrlAnalysisResult.estado == "incompleto"`.

## 3. Salida Completa
- `status` (`"ok"` | `"incomplete"` | `"error"`), `level`, `score`, `summary`, `is_critical_combo`.
