# 📘 Guía Técnica de Referencia: Señales y Reglas de Análisis Estático de URLs

> [!NOTE]
> **Documentación Técnica de Referencia:** Este documento constituye material de consulta técnica para desarrolladores, auditores y mantenimiento del sistema. No forma parte del prompt inyectado por defecto al modelo de lenguaje ni representa un mecanismo de consulta bajo demanda en tiempo de ejecución.

---

## 1. Principio Fundamental: Cero Red (Zero Network)
El análisis estructural de enlaces implementado en `scripts/url_analyzer.py` opera de forma **100% estática**:
- No resuelve nombres de dominio mediante DNS (`socket.gethostbyname`).
- No abre conexiones de red, sockets ni realiza peticiones HTTP/HTTPS (`urllib.request`, `requests`).
- No expande acortadores de URL (`bit.ly`, `tinyurl`) ni sigue redirecciones de servidor (códigos HTTP 301/302).
- Todas las detecciones se realizan analizando sintácticamente las componentes de la cadena de texto (`scheme`, `netloc`, `path`, `query`, `fragment`).

---

## 2. Catálogo Canónico de Reglas de Enlace

### `REGLA-URL-01`: Host Basado en Dirección IP Numérica
- **Patrón:** El destino utiliza directamente una dirección IPv4 o IPv6 en lugar de un nombre de dominio calificado (FQDN).
  - Ejemplo: `http://192.168.1.100/login` o `http://[2001:db8::1]/auth`.
- **Riesgo:** Los atacantes utilizan direcciones IP directas para eludir listas de bloqueo basadas en nombres de dominio o en infraestructura efímera sin registro DNS formal.
- **Implementación:** `scripts.url_analyzer.is_ip_host(hostname)`.

---

### `REGLA-URL-02`: Subdominio Engañoso con Marca o Término de Seguridad
- **Patrón:** Un nombre de marca conocida (ej. `mercadopago`, `galicia`, `santander`, `afip`) o un término de seguridad/validación (`validacion`, `verificacion`, `seguridad`, `actualizacion`, `soporte`, `pagos`) se encuentra en un subdominio, mientras que el dominio base registrable pertenece a otra entidad.
  - Ejemplo: `https://mercadopago.validacion-cuenta.com/login` (el dominio real es `validacion-cuenta.com`, no `mercadopago.com`).
  - Ejemplo: `https://bancogalicia.seguridad-online.net/auth`.
- **Riesgo:** Ingeniería social orientada a confundir al usuario visualmente en pantallas pequeñas o navegadores móviles.
- **Implementación:** `scripts.url_analyzer.check_misleading_subdomains(hostname)`.

---

### `REGLA-URL-03`: Uso de Codificación Punycode o Homóglifos
- **Patrón:** El nombre de dominio contiene prefijos Punycode (`xn--`) o caracteres no ASCII que simulan visualmente caracteres latinos estándar (ataque homógrafo de IDN).
  - Ejemplo: `https://xn--bncogalicia-77a.com/` (simula `bancogalicia.com` utilizando un caracter cirílico o acentuado).
- **Riesgo:** Suplantación de identidad prácticamente imperceptible a simple vista.
- **Implementación:** `scripts.url_analyzer.has_punycode_or_homoglyphs(hostname)`.

---

### `REGLA-URL-04`: Credenciales Embebidas en la URL (Userinfo)
- **Patrón:** La URL incluye datos de autenticación en la autoridad de red con formato `usuario:contraseña@host`.
  - Ejemplo: `https://cliente:clave123@portal-acceso.com/home`.
- **Riesgo:** Maniobras para ofuscar el host de destino o inducir al usuario a creer que accede a una sesión preautenticada, o extracción de credenciales en texto plano.
- **Implementación:** Verificación de `parsed.username` o `parsed.password` en `urllib.parse`.

---

### `REGLA-URL-05`: Dominio en Extensión TLD Desechable o de Bajo Costo
- **Patrón:** El dominio base utiliza un TLD genérico frecuentemente adquirido en campañas masivas de fraude digital por su bajo costo o nula verificación de titularidad.
  - TLDs identificados: `.xyz`, `.top`, `.online`, `.site`, `.club`, `.buzz`, `.click`, `.rest`, `.cam`, `.vip`, `.work`, `.cfd`.
  - Ejemplo: `https://promocion-aniversario.xyz/sorteo`.
- **Riesgo:** Alta correlación con dominios efímeros creados exclusivamente para una campaña de spam/phishing.
- **Implementación:** `scripts.url_analyzer.SUSPICIOUS_TLDS`.

---

## 3. Señales Informativas Adicionales
- **Protocolo HTTP sin cifrado:** Advertencia de que el canal de comunicación no cuenta con cifrado TLS/SSL.
- **Aclaración sobre HTTPS:** El uso de HTTPS únicamente garantiza cifrado en tránsito; **no avala la legitimidad del sitio web**, ya que los atacantes obtienen certificados gratuitos (Let's Encrypt) con facilidad.
- **Parámetros Sensibles en Query String:** Presencia de parámetros como `token`, `clave`, `password`, `pwd`, `pin`, `otp`, `cbu`, `cvu` en la URL.
