---
name: asignar-nivel-riesgo
description: >-
  Asigna en Python el nivel de riesgo cualitativo (ALTO, MEDIO, BAJO o INDETERMINADO)
  aplicando los umbrales documentados, las combinaciones críticas y los criterios de
  salvaguarda ante análisis incompletos, sin convertir fallos en riesgo bajo.
tool_name: tool_asignar_nivel_riesgo
allowed_agents:
  - evaluador
---

# 🏷️ Skill: Asignar Nivel de Riesgo (`asignar-nivel-riesgo`)

## 1. Única Responsabilidad
Determinar y fijar en Python el nivel de riesgo cualitativo final de la evaluación utilizando la función `RiskClassifier.assign_risk_level`. Aplica los umbrales documentados en `policy.json` (`alto >= 50`, `medio >= 20`), las combinaciones críticas de severidad y las salvaguardas de seguridad para entradas insuficientes o análisis de especialistas incompletos.

## 2. Qué Recibe (Entrada)
Recibe a través de la herramienta `tool_asignar_nivel_riesgo`:
- `confirm_scored`: parámetro booleano obligatorio (`true`) que confirma que el cálculo numérico previo fue ejecutado mediante `tool_calcular_puntaje`.
- Opera directamente sobre el puntaje calculado y los hallazgos validados de la sesión, impidiendo que el modelo altere arbitrariamente el nivel de riesgo.

## 3. Qué Devuelve (Salida)
Devuelve un diccionario estructurado con:
- `status`: `"ok"` si la asignación se realizó, `"incomplete"` si el análisis previo fue parcial o incompleto, o `"error"` ante fallo de precondiciones.
- `level`: cadena con uno de los 4 niveles permitidos: `"ALTO"`, `"MEDIO"`, `"BAJO"` o `"INDETERMINADO"`.
- `score`: puntaje numérico verificado (0-100).
- `summary`: resumen explicativo oficial del nivel de riesgo.
- `is_critical_combo`: booleano que indica si se activó alguna combinación crítica que eleva el riesgo a ALTO aun con puntaje menor a 50.

## 4. Reglas y Criterios de Clasificación
- **ALTO:**
  1. Puntaje calculado `>= 50` puntos (umbral `thresh_alto`).
  2. Presencia confirmada de tentativa de manipulación del agente (`SEC-PROMPT-INJECTION`).
  3. Activación de combinaciones críticas:
     - Amenaza de bloqueo (`ING-AMENAZA-BLOQUEO`) + Pedido de claves (`FRA-CAPTURA-CREDENCIALES` o URL sospechosa).
     - Pedido de claves (`FRA-CAPTURA-CREDENCIALES`) + URL sospechosa.
     - (Amenaza de bloqueo o Urgencia) + Pedido de claves.
     - Fraude de pago anticipado (`FRA-PAGO-ANTICIPADO`).
     - Maniobra de DEBIN engañoso (`FRA-DEBIN-ENGANOSO`).
- **MEDIO:**
  - Puntaje calculado `>= 20` y `< 50` puntos sin combinación crítica (señales aisladas de alarma como urgencia sin amenaza, enlaces no verificados o menciones institucionales).
- **BAJO:**
  - Puntaje calculado `< 20` puntos y ausencia de combinaciones críticas o análisis incompletos.
  - *Advertencia obligatoria:* la ausencia de indicadores conocidos de fraude no constituye una garantía de que el mensaje sea auténtico.
- **INDETERMINADO:**
  - Contenido demasiado breve o fragmentado (< 15 caracteres o llamado a la acción aislado < 45 caracteres sin evidencia).
  - Análisis de mensaje con categorías obligatorias omitidas o no revisadas (`MessageAnalysisResult.estado == "incompleto"`).
  - Análisis de URLs con enlaces omitidos o direcciones no analizables (`UrlAnalysisResult.estado == "incompleto"`).
  - *Regla inviolable:* **Ningún resultado incompleto o con error técnico puede clasificarse como RIESGO BAJO**.

## 5. Límites y Seguridad
- El nivel de riesgo debe proceder exclusivamente de la lógica Python y verificarse contra el contrato de salida.
- Requiere como precondición obligatoria haber ejecutado previamente `tool_calcular_puntaje`.

