"""
Módulo de Análisis Estático de URLs para Detective de Estafas Digitales.

Este módulo extrae y analiza URLs presentes en mensajes sin visitarlas ni
realizar consultas externas (Zero Network / Zero External Requests).
Cumple con el principio de mínimo privilegio y ejecución puramente estática.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any, Dict, List
import urllib.parse

# Expresión regular robusta para extracción de URLs sin navegar a ellas
URL_REGEX = re.compile(
    r"""(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))""",
    re.VERBOSE,
)

COMMON_TARGET_BRANDS = [
    "mercadopago",
    "mercadolibre",
    "bancogalicia",
    "galicia",
    "santander",
    "bbva",
    "banconacion",
    "bancoprovincia",
    "bancomacro",
    "cuentadni",
    "uala",
    "afip",
    "arca",
    "anses",
    "miargentina",
    "correoargentino",
    "whatsapp",
    "google",
    "apple",
    "microsoft",
    "netflix",
    "instagram",
    "binance",
    "personal",
    "flow",
]

# Términos típicamente usados en subdominios para simular portales oficiales de validación
DECEPTIVE_SECURITY_KEYWORDS = [
    "validacion",
    "verificacion",
    "seguridad",
    "actualizacion",
    "soporte",
    "reclamos",
    "atencion",
    "pagos",
    "tramites",
    "facturacion",
    "cobros",
]

# TLDs comúnmente asociados a dominios desechables o de bajo costo para campañas de phishing
SUSPICIOUS_TLDS = {
    "xyz", "top", "online", "site", "club", "buzz", "click", "rest", "cam", "vip", "work", "cfd"
}


def extract_urls(text: str) -> List[str]:
    """
    Extrae todas las URLs presentes en el texto recibido.
    No visita ninguna dirección ni envía paquetes de red.
    """
    if not text:
        return []

    matches = URL_REGEX.findall(text)
    urls: List[str] = []
    for match in matches:
        raw_url = match[0].strip()
        # Normalizar si empieza con www. sin esquema
        if raw_url.lower().startswith("www."):
            raw_url = "http://" + raw_url
        if raw_url not in urls:
            urls.append(raw_url)
    return urls


def is_ip_host(hostname: str) -> bool:
    """
    Determina de forma estática si el hostname es una dirección IP (IPv4 o IPv6).
    """
    if not hostname:
        return False
    # Remover corchetes en IPv6 si los tiene
    cleaned = hostname.strip("[]")
    try:
        ipaddress.ip_address(cleaned)
        return True
    except ValueError:
        return False


def has_punycode_or_homoglyphs(hostname: str) -> bool:
    """
    Verifica si el dominio contiene punycode ('xn--') o caracteres no ASCII
    que puedan representar ataques de homóglifos (IDN homograph attack).
    """
    if not hostname:
        return False
    lower_host = hostname.lower()
    if "xn--" in lower_host:
        return True
    # Revisar caracteres fuera del rango ASCII imprimible
    try:
        lower_host.encode("ascii")
    except UnicodeEncodeError:
        return True
    return False


def check_misleading_subdomains(hostname: str) -> List[str]:
    """
    Detecta si una marca conocida está siendo utilizada como subdominio
    para engañar al usuario haciéndole creer que el sitio pertenece a dicha marca.
    Ejemplo: galicia.seguridad-bancaria.online (el dominio real es seguridad-bancaria.online)
    """
    findings: List[str] = []
    if not hostname:
        return findings

    parts = hostname.lower().split(".")
    if len(parts) < 3:
        # No tiene subdominios relevantes (ej: mercadopago.com)
        return findings

    # El dominio principal típicamente son los últimos 2 componentes (salvo casos como .com.ar)
    subdomains = ".".join(parts[:-2])
    base_domain = ".".join(parts[-2:])

    for brand in COMMON_TARGET_BRANDS:
        if brand in subdomains and brand not in base_domain:
            findings.append(
                f"Uso engañoso de la marca '{brand}' en el subdominio mientras el dominio real es '{base_domain}'."
            )

    # Detección de términos engañosos de validación/seguridad en subdominios
    for kw in DECEPTIVE_SECURITY_KEYWORDS:
        if kw in subdomains and kw not in base_domain:
            findings.append(
                f"Uso de términos engañosos de seguridad/validación ('{kw}') en subdominio con dominio no verificado '{base_domain}'."
            )
            break
    return findings


def analyze_single_url(raw_url: str) -> Dict[str, Any]:
    """
    Realiza una auditoría estática completa de una URL individual.
    """
    findings: List[str] = []
    parsed = urllib.parse.urlparse(raw_url)
    scheme = parsed.scheme.lower() if parsed.scheme else "desconocido"
    hostname = parsed.hostname.lower() if parsed.hostname else ""
    port = parsed.port

    # 1. Análisis de Protocolo
    if scheme == "http":
        findings.append("Utiliza HTTP sin cifrado (tráfico legible en texto plano).")
    elif scheme == "https":
        # Aclaración técnica: HTTPS no implica legitimidad
        findings.append("Utiliza HTTPS (cifrado en tránsito, pero NO garantiza legitimidad del sitio).")

    # 2. Análisis de Host como IP directa
    is_ip = is_ip_host(hostname)
    if is_ip:
        findings.append(
            f"El enlace apunta directamente a una dirección IP ({hostname}) en lugar de un nombre de dominio legítimo."
        )

    # 3. Análisis de Homóglifos y Punycode
    has_punycode = has_punycode_or_homoglyphs(hostname)
    if has_punycode:
        findings.append(
            "El dominio utiliza codificación Punycode o caracteres homóglifos (posible técnica de suplantación visual)."
        )

    # 4. Análisis de Subdominios engañosos
    subdomain_findings = check_misleading_subdomains(hostname)
    findings.extend(subdomain_findings)

    # 5. Detección de credenciales embebidas (RFC 3986 userinfo)
    has_userinfo = bool(parsed.username or parsed.password)
    if has_userinfo:
        findings.append(
            "La URL contiene credenciales embebidas (patrón usuario:contraseña@host), técnica clásica de ofuscación de destino."
        )

    # 6. Detección de parámetros sospechosos en Query String
    query_params = urllib.parse.parse_qs(parsed.query)
    sensitive_param_names = {"token", "clave", "password", "pwd", "pin", "otp", "cbu", "cvu"}
    found_sensitive_params = sensitive_param_names.intersection({p.lower() for p in query_params.keys()})
    if found_sensitive_params:
        findings.append(
            f"La URL transporta parámetros sensibles en la dirección: {', '.join(found_sensitive_params)}."
        )

    # 7. TLD de alto riesgo o desechable
    if hostname and "." in hostname:
        tld = hostname.split(".")[-1]
        if tld in SUSPICIOUS_TLDS:
            findings.append(
                f"El dominio utiliza una extensión de dominio de bajo costo frecuentemente asociada a campañas efímeras de spam/phishing (.{tld})."
            )

    return {
        "raw_url": raw_url,
        "scheme": scheme,
        "domain": hostname or "no_identificado",
        "port": port,
        "is_ip_address": is_ip,
        "has_punycode": has_punycode,
        "has_userinfo": has_userinfo,
        "findings": findings,
    }


def analyze_urls_in_text(text: str) -> List[Dict[str, Any]]:
    """
    Punto de entrada para extraer y analizar todas las URLs en un texto.
    """
    urls = extract_urls(text)
    return [analyze_single_url(u) for u in urls]
