---
name: calcular-puntaje
description: >-
  Calcula en Python el puntaje heurístico de severidad acumulada (0-100) y genera la lista
  de reglas activadas sobre los hallazgos reunidos, aplicando estrictamente las ponderaciones
  documentadas sin que el modelo invente, altere o sume puntos.
tool_name: tool_calcular_puntaje
allowed_agents:
  - evaluador
---

# ⚖️ Skill: Calcular Puntaje (`calcular-puntaje`)

## 1. Única Responsabilidad
Ejecutar estrictamente en Python la función de cálculo de puntaje (`RiskClassifier.calculate_score`) sobre los indicadores de texto y los análisis de URLs reunidos por `tool_reunir_hallazgos`. El puntaje es una escala heurística de severidad acumulada (0 a 100 puntos) basada en la política documentada (`config/policy.json`); **no representa una probabilidad matemática o estadística de estafa**.

## 2. Qué Recibe (Entrada)
Recibe a través de la herramienta `tool_calcular_puntaje`:
- `confirm_gathered`: parámetro booleano obligatorio (`true`) que confirma que los hallazgos fueron reunidos previamente mediante `tool_reunir_hallazgos`.
- La herramienta opera exclusivamente sobre el estado local de hallazgos unificados de la sesión, garantizando que el modelo de IA no intervenga en la suma aritmética ni en la ponderación de las reglas.

## 3. Qué Devuelve (Salida)
Devuelve un diccionario estructurado con:
- `status`: `"ok"` si el cálculo se completó, `"incomplete"` si los hallazgos disponibles provienen de un análisis incompleto o contenido insuficiente, o `"error"` ante fallo de precondiciones.
- `score`: entero acotado entre 0 y 100.
- `activated_rules`: lista de cadenas de texto con la trazabilidad explícita de cada regla activada y sus puntos correspondientes (por ejemplo, `REGLA-FRA-01 (+40 pts): ...`, `REGLA-URL-01 (+30 pts): ...`).
- `is_indeterminate`: booleano que indica si el contenido fue insuficiente (< 15 caracteres o llamado a la acción aislado < 45 caracteres sin evidencia).
- `summary`: descripción preliminar del cálculo.

## 4. Reglas Ponderadas Reutilizadas (`policy.json`)
- **Seguridad IA:** `REGLA-SEC-01` (+45 pts) por Prompt Injection.
- **Fraude Financiero:** `REGLA-FRA-01` (+40 pts) por captura de claves/OTP; `REGLA-FRA-02` (+35 pts) por pago anticipado; `REGLA-FRA-03` (+25 pts) por premio inesperado; `REGLA-FRA-04` (+30 pts) por maniobra DEBIN.
- **Ingeniería Social:** `REGLA-ING-01` (+35 pts) por amenaza de bloqueo/suspensión; `REGLA-ING-02` (+15 pts) por urgencia/presión temporal; `REGLA-SUP-01` (+15 pts) por invocación de entidad en contexto coercitivo.
- **URLs Sospechosas:** `REGLA-URL-01` (+30 pts) por IP numérica; `REGLA-URL-02` (+30 pts) por subdominio engañoso; `REGLA-URL-03` (+25 pts) por Punycode/homóglifos; `REGLA-URL-04` (+20 pts) por credenciales embebidas; `REGLA-URL-05` (+20 pts) por TLD de bajo costo/alta incidencia sin subdominio previo.
- El puntaje se acota rígidamente a un valor máximo de 100 (`min(score, 100)`).

## 5. Límites y Seguridad
- **El modelo NO calcula los números:** todo cálculo numérico es determinístico en Python. Los valores reportados al usuario se validan contractualmente contra la salida de la herramienta Python.
- No asigna el nivel de riesgo final (`ALTO`, `MEDIO`, `BAJO`, `INDETERMINADO`), tarea delegada a la skill `asignar-nivel-riesgo`.
- Requiere como precondición obligatoria haber ejecutado exitosamente `tool_reunir_hallazgos`.

