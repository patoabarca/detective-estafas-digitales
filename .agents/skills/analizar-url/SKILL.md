---
name: analizar-url
description: >-
  Analiza de forma estrictamente estática la estructura sintáctica de las direcciones
  web (URLs) extraídas en la sesión actual para detectar IP directa, subdominios
  engañosos, Punycode/homóglifos, credenciales embebidas, parámetros sensibles y TLDs
  de bajo costo, sin visitar los enlaces ni realizar conexiones de red.
tool_name: tool_analizar_url
allowed_agents:
  - analizador_enlaces
---

# 🌐 Skill: Analizar Estructura de URL (`analizar-url`)

## 1. Única Responsabilidad
Auditar de manera 100% estática y local las direcciones web (URLs) extraídas en la solicitud actual utilizando las verificaciones existentes en `scripts/url_analyzer.py` (`analyze_single_url`, `is_ip_host`, `has_punycode_or_homoglyphs`, `check_misleading_subdomains`), identificando las señales y reglas `REGLA-URL-01` a `REGLA-URL-05` sin visitar ningún enlace ni realizar consultas de red.

## 2. Qué Recibe (Entrada)
Recibe a través de la herramienta `tool_analizar_url`:
- `url_ids`: lista acotada de identificadores de enlaces de la sesión actual (por ejemplo, `["URL-1", "URL-2"]`) o `["ALL"]` para procesar en una sola llamada todos los enlaces extraídos en la sesión actual, evitando un turno de modelo por cada URL.
- La herramienta recupera siempre las direcciones originales directamente del estado local validado (`PreparationSessionContext`), **rechazando cualquier dirección o identificador inventado o sustituido por el modelo**.

## 3. Qué Devuelve (Salida)
Devuelve un diccionario estructurado y sanitizado para el modelo con:
- `status`: `"ok"` si todos los enlaces solicitados se analizaron estáticamente, `"partial_or_unparseable"` si alguna dirección estaba malformada o no pudo analizarse por completo, `"no_links"` si no había enlaces, o `"tool_error"` ante un fallo técnico.
- `processed_count`: cantidad de enlaces procesados en la llamada.
- `total_session_urls`: cantidad total de enlaces extraídos en la sesión.
- `results`: lista de objetos por cada enlace (`url_id`, `masked_url`, `domain`, `status`, `signals`, `rule_ids`, `findings`, `ocr_warnings`).
- `warnings`: advertencias globales (incluyendo que la ausencia de señales sintácticas nunca garantiza que un sitio web sea legítimo o seguro, y las advertencias de distorsión OCR sin autocorregir la URL).

## 4. Reglas y Señales Existentes que Identifica
- `REGLA-URL-01`: El enlace apunta directamente a una dirección IP numérica (IPv4 o IPv6) en lugar de un dominio (`is_ip_address == True`).
- `REGLA-URL-02`: Uso engañoso de una marca conocida o término de seguridad/validación en el subdominio mientras el dominio base real es otro (`check_misleading_subdomains`).
- `REGLA-URL-03`: El dominio utiliza codificación Punycode (`xn--`) o caracteres homóglifos no ASCII (`has_punycode == True`).
- `REGLA-URL-04`: La URL contiene credenciales embebidas con formato `usuario:contraseña@host` (`has_userinfo == True`).
- `REGLA-URL-05`: El dominio emplea una extensión TLD frecuentemente desechable (`.xyz`, `.top`, `.online`, `.site`, `.club`, `.buzz`, `.click`, `.rest`, `.cam`, `.vip`, `.work`, `.cfd`) sin subdominio engañoso previo.
- Señales informativas adicionales: protocolo `http` sin cifrado, aclaración sobre `https` y presencia de parámetros sensibles en la query string (`token`, `clave`, `password`, `pwd`, `pin`, `otp`, `cbu`, `cvu`).

## 5. Límites y Controles de Seguridad
- **Cero Red (Zero Network):** prohibido realizar peticiones HTTP/HTTPS, resoluciones DNS, aperturas de sockets, expansión de acortadores o seguimiento de redirecciones.
- **Prohibición de autocorrección OCR:** si una URL proviene de OCR y presenta advertencias de distorsión tipográfica, se conserva la dirección original tal como fue extraída junto con sus advertencias.
- **Privacidad hacia el modelo:** las respuestas de la herramienta que vuelven al modelo externo enmascaran credenciales embebidas, correos, DNI, CBU/CVU y valores de parámetros sensibles en la URL (`sanitize_url_for_external_llm`), mientras el estado local conserva el resultado completo para el informe local.

