---
name: extraer-enlaces
description: >-
  Identifica y extrae de manera estática todas las direcciones web (URLs) presentes en
  un texto recibido o extraído por OCR, sin visitar los enlaces ni realizar consultas
  de red.
tool_name: tool_extraer_enlaces
allowed_agents:
  - preparador
---

# 🔗 Skill: Extraer Enlaces (`extraer-enlaces`)

## 1. Única Responsabilidad
Analizar estáticamente el texto disponible en el contexto de preparación para identificar, normalizar y listar cualquier dirección web (URL) presente, reportando hallazgos sintácticos preliminares sin realizar ninguna conexión de red.

## 2. Qué Recibe (Entrada)
Recibe a través de la herramienta `tool_extraer_enlaces` la solicitud de inspeccionar el texto activo de la sesión (ya sea el texto ingresado por el usuario o el texto recién extraído por OCR). Opcionalmente acepta el parámetro booleano `include_static_Metadata` (por defecto `true`).

## 3. Qué Devuelve (Salida)
Devuelve un diccionario estructurado (`LinkExtractionToolOutput`) con:
- `status`: `"ok"` cuando se encontraron uno o más enlaces, `"no_links"` cuando el texto fue analizado correctamente pero no contiene ningún enlace, o `"tool_error"` si ocurrió un error inesperado.
- `links_count`: cantidad entera de enlaces únicos detectados (`0` si no hay enlaces).
- `urls`: lista de cadenas con las URLs extraídas en texto plano.
- `url_details`: lista de diccionarios con el desglose estático de cada URL (`raw_url`, `scheme`, `domain`, `is_ip_address`, `has_punycode`, `findings`).
- `warnings`: advertencias adicionales asociadas a la lectura de enlaces.
- `error_message`: `null` en operación normal, o descripción del fallo si `status == "tool_error"`.

## 4. Herramienta Python Utilizada
- Función registrada: `tool_extraer_enlaces` en `agents/tools/preparation_tools.py`.
- Reutiliza internamente `extract_urls` y `analyze_urls_in_text` de `scripts/url_analyzer.py`.

## 5. Límites y Manejo de Errores
- **Política estricta Zero Network:** la herramienta **nunca** abre, descarga, resuelve por DNS ni envía peticiones HTTP/HTTPS a las URLs encontradas.
- **Diferenciación explícita:** cuando un mensaje no tiene enlaces, devuelve `status: "no_links"` y `urls: []`, lo cual es un resultado válido y normal (no un error de herramienta ni de entrada).
