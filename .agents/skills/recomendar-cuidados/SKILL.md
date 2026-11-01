---
name: recomendar-cuidados
description: >-
  Selecciona las recomendaciones preventivas del sistema adecuadas según el nivel
  de riesgo determinado y la presencia de enlaces o pedidos de credenciales, sin inventar
  contactos, números telefónicos ni instituciones no mencionadas.
tool_name: tool_recomendar_cuidados
allowed_agents:
  - evaluador
---

# 🛡️ Skill: Recomendar Cuidados (`recomendar-cuidados`)

## 1. Única Responsabilidad
Seleccionar y estructurar las recomendaciones preventivas del sistema correspondientes al caso analizado utilizando `ReportGenerator.get_recommendations`. Las medidas sugeridas se adaptan de forma precisa al nivel de riesgo (`ALTO`, `MEDIO`, `BAJO`, `INDETERMINADO`), a la presencia de enlaces en el mensaje y a la existencia de solicitudes de credenciales o transferencias, denominándolas expresamente como "recomendaciones preventivas del sistema" sin atribuirlas a fuentes institucionales salvo que una entidad oficial comprobada haya sido identificada.

## 2. Qué Recibe (Entrada)
Recibe a través de la herramienta `tool_recomendar_cuidados`:
- `confirm_level_assigned`: parámetro booleano obligatorio (`true`) que confirma que el nivel de riesgo fue asignado previamente mediante `tool_asignar_nivel_riesgo`.
- La herramienta consulta el estado validado de la sesión (nivel de riesgo, presencia de URLs y presencia de solicitudes de claves/tokens).

## 3. Qué Devuelve (Salida)
Devuelve un diccionario estructurado con:
- `status`: `"ok"` si las recomendaciones fueron seleccionadas, o `"error"` si faltó la asignación de nivel previa.
- `recommendations_count`: cantidad de recomendaciones preventivas provistas.
- `recommendations`: lista de cadenas de texto con las medidas concretas aplicables.
- `context_flags`: indicadores de contexto que motivaron las recomendaciones (`has_urls`, `has_credentials`, `risk_level`).

## 4. Conjunto de Recomendaciones Preventivas del Sistema Reutilizadas
- **Para Riesgo ALTO o MEDIO:**
  - *Si hay URLs:* "NO hagas clic en ninguno de los enlaces incluidos en el mensaje."
  - *Si hay pedido de datos/claves:* "NUNCA compartas contraseñas, tokens de seguridad, PIN ni códigos de 6 dígitos que te lleguen por SMS o WhatsApp."
  - *Generales de precaución:*
    - "No respondas el mensaje ni continúes la comunicación por esa vía."
    - "Verificá la situación comunicándote directamente con la entidad a través de sus canales públicos (sitio web oficial, teléfono en el dorso de la tarjeta o sucursal bancaria)."
    - "Si sospechás que diste algún dato confidencial, cambiá inmediatamente tus claves desde otro dispositivo y comunicate con el área de fraudes de tu banco."
- **Para Riesgo INDETERMINADO:**
  - "El mensaje no contiene suficiente información para evaluar su seguridad. Evitá compartir datos personales hasta verificar el remitente."
- **Para Riesgo BAJO:**
  - "Aunque no se detectaron señales evidentes de alarma, mantené siempre la precaución."
  - "Recordá que ningún organismo oficial ni banco solicita contraseñas por mensaje directo."

## 5. Límites y Seguridad
- **Prohibición de inventar contactos:** no genera números de teléfono, correos electrónicos, cuentas de mensajería ni alias falsos o inventados.
- Denominación rigurosa: se presentan como recomendaciones preventivas del sistema, promoviendo que el usuario recurra a canales de atención verificados de forma independiente.
- Requiere como precondición que `tool_asignar_nivel_riesgo` haya sido ejecutada previamente.

