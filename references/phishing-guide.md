# Guía Teórica de Phishing e Ingeniería Social

Esta guía proporciona el marco conceptual utilizado por el **Detective de Estafas Digitales** para la detección y clasificación de amenazas informáticas orientadas a personas.

---

## 1. Definiciones Fundamentales

### Phishing
Técnica de ciberdelincuencia donde un atacante se hace pasar por una entidad legítima (banco, empresa de correo, organismo estatal) mediante medios digitales para engañar al usuario y conseguir que revele información confidencial (contraseñas, números de tarjeta de crédito, tokens).

### Variantes Principales
- **Smishing (SMS Phishing):** Ataques perpetrados a través de mensajes de texto SMS. Suele incluir enlaces cortos y mensajes alarmantes sobre paquetes o cuentas bancarias.
- **WhatsApp Scam:** Ataques que explotan la confianza de la aplicación de mensajería instantánea. Común en robo de cuentas (secuestro de WhatsApp mediante el código de 6 dígitos) o suplantación de contactos de agenda pidiendo dinero por emergencia.
- **Spear Phishing:** Phishing dirigido y personalizado hacia una persona u organización específica con información previa obtenida mediante ingeniería social.
- **Vishing (Voice Phishing):** Ataques telefónicos donde simulan ser agentes de soporte técnico, bancos o personal de ANSES para guiar a la persona a un cajero automático o extraer el token.

---

## 2. Vectores Psicológicos de la Ingeniería Social

La ingeniería social no ataca vulnerabilidades de software, sino vulnerabilidades cognitivas humanas:

| Disparador Psicológico | Mecanismo de Explotación | Ejemplo Típico |
| :--- | :--- | :--- |
| **Miedo / Coerción** | Amenaza de consecuencias graves o legales inmediatas | "Orden de embargo judicial si no paga en 24h" |
| **Urgencia Temporal** | Reducir el tiempo disponible para razonar lógicamente | "Quedan 10 minutos para validar su clave" |
| **Avaricia / Oportunidad** | Ofrecer recompensas extraordinarias a cambio de acciones mínimas | "Ganaste 1 millón de pesos sin participar" |
| **Empatía / Solidaridad** | Fingir una emergencia médica o económica familiar | "Mamá cambié el número, necesito plata urgente" |
| **Autoridad** | Simular figuras estatales o bancarias respetadas | "Comunicado oficial AFIP / Banco Central" |

---

## 3. Anatomía de un Enlace Malicioso

Los atacantes recurren a trucos en las URLs para hacerlas parecer fidedignas:

1. **Typosquatting:** Registro de dominios con errores ortográficos mínimos (`banc0galicia.com`, `mercadopaqo.com`).
2. **Subdominio de distracción:**
   `https://banco.santander.com.ar.servidor-malicioso.com/login`
   - El dominio real es `servidor-malicioso.com`.
   - `banco.santander.com.ar` es solo un subdominio bajo control del atacante.
3. **Punycode / Homoglyph Attack:**
   Uso de caracteres visualmente idénticos del alfabeto cirílico u otros alfabetos (`а` cirílica vs `a` latina). Se codifican como `xn--...` en DNS.
4. **Acortadores opacos:** Enlaces tipo `bit.ly/3xYz` que ocultan el destino real para eludir filtros visuales.

---

## 4. El Principio de "HTTPS No Significa Seguro"

Una concepción errónea común es creer que el candado de HTTPS indica que el sitio es de confianza.

> **Advertencia Técnica:**
> HTTPS solo garantiza que la comunicación entre el navegador del usuario y el servidor está cifrada en tránsito. Cualquier atacante puede obtener un certificado SSL gratuito (por ejemplo vía Let's Encrypt) para un dominio fraudulento.
> **HTTPS significa que la conexión es cifrada, no que el destinatario sea honesto.**
