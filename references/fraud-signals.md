# Catálogo de Señales de Fraude e Ingeniería Social

Este catálogo documenta los patrones e indicadores observables en mensajes digitales fraudulentos (WhatsApp, SMS, correo electrónico, redes sociales). Está orientado a la realidad de ciberestafas en Hispanoamérica, con especial énfasis en Argentina.

---

## 1. Urgencia Artificial y Amenazas de Bloqueo

### Descripción
El atacante induce un estado emocional de alerta o pánico en la víctima para forzar una decisión apresurada antes de que pueda reflexionar o consultar con terceros.

### Expresiones Comunes
- "Su cuenta será bloqueada en las próximas 2 horas."
- "Detectamos un acceso no autorizado desde Córdoba/Rusia."
- "Último aviso antes de suspensión definitiva."
- "Evite el cierre inmediato de su tarjeta/cuenta."

### Por qué es sospechoso
Las entidades bancarias y plataformas formales poseen protocolos de seguridad que no exigen acciones inmediatas mediante clics en enlaces no verificados para evitar bajas de servicio.

---

## 2. Solicitud de Credenciales y Factores de Autenticación (OTP)

### Descripción
Tentativa de capturar contraseñas, PIN de cajero, tokens de seguridad o códigos de 6 dígitos enviados por SMS/WhatsApp.

### Expresiones Comunes
- "Para validar su identidad ingrese su clave de home banking."
- "Reenvíenos el código de 6 dígitos que le llegó a su celular para confirmar la transferencia."
- "Ingrese su Token de Seguridad para cancelar el débito."

### Regla de Oro
**Ningún banco, billetera virtual ni soporte de WhatsApp solicita jamás el código de verificación o contraseña personal.**

---

## 3. Premios Inesperados y Promociones Extraordinarias

### Descripción
Promesas de beneficios monetarios desmedidos, premios de sorteos en los que nunca se participó o subsidios estatales ficticios.

### Expresiones Comunes
- "¡Felicitaciones! Ha ganado un Smart TV y $500.000 en el sorteo aniversario."
- "Plan Mi Argentina / ANSES: Su cobro del IFE/Bono extraordinario está disponible."
- "Obtenga 50 GB de internet gratis haciendo clic aquí."

### Indicador clave
Suelen condicionar la entrega del beneficio al pago previo de "gastos administrativos" o a la entrega de datos bancarios.

---

## 4. Fraude de Pago Anticipado (Advance Fee Fraud)

### Descripción
Se le solicita a la víctima abonar una tarifa mínima de envío, impuestos de aduana o costos de escribanía para liberar una suma mayor o un paquete retenido.

### Expresiones Comunes
- "Paquete de Correo Argentino retenido por tasa de aduana de $3.250."
- "Abonar arancel de liberación para transferir los fondos."

---

## 5. Engaño de DEBIN y Transferencia Inversa

### Descripción
Muy frecuente en ventas por Marketplace o WhatsApp en Argentina. El estafador afirma haber enviado dinero de más o envía una solicitud de DEBIN (Débito Inmediato) haciendo creer a la víctima que está aceptando una acreditación.

### Expresiones Comunes
- "Te transferí por error de más, aceptá la solicitud para devolverlo."
- "Te mandé un DEBIN, aceptalo en tu banco para que te entre el pago."

---

## 6. Suplantación de Organismos Oficiales y Entidades

### Entidades frecuentemente suplantadas en Argentina:
- **Bancos:** Banco Galicia, Santander, Banco Nación, BBVA, Banco Provincia, Banco Macro, Brubank.
- **Billeteras Digitales:** Mercado Pago, Ualá, Cuenta DNI, Personal Pay.
- **Organismos Públicos:** AFIP / ARCA, ANSES, Mi Argentina, Correo Argentino, PAMI, Poder Judicial.
- **Servicios:** Netflix, Spotify, Cablevisión/Flow, Edesur, Edenor.

---

## 7. Anomalías en Enlaces (URLs)

1. **Uso de IP directa:** En lugar de nombre de dominio (ej: `http://192.168.1.1/login`).
2. **Subdominios engañosos:** `https://mercadopago.com.seguridad-cuenta.xyz` (el dominio real es `seguridad-cuenta.xyz`).
3. **Punycode / Caracteres homóglifos:** Uso de letras cirílicas o acentos para simular dominios legítimos (`xn--...`).
4. **Acortadores de URL sin contexto:** `bit.ly`, `tinyurl.com` en comunicaciones supuestamente bancarias.
5. **Protocolo no cifrado (HTTP simple):** Enlaces que solicitan datos mediante `http://`.
