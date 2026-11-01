"""
Módulo de Minimización y Ocultamiento Preventivo de Datos Sensibles (PII Masking).

Antes de enviar texto al proveedor externo de IA (Google Gemini API):
1. Oculta patrones evidentes de datos personales o bancarios innecesarios para la
   orquestación/preparación (CBU/CVU de 22 dígitos, tarjetas de 13-19 dígitos,
   direcciones de correo personales, teléfonos y números de DNI/CUIT).
2. Conserva intactas las direcciones web (URLs) y la estructura del mensaje para
   que el modelo y las herramientas puedan identificar enlaces y señales contextuales.
3. El texto original sin enmascarar se conserva exclusivamente en memoria RAM local
   para el análisis determinístico local, sin escribirse en logs.

Nota de honestidad técnica: El ocultamiento por expresiones regulares reduce la
exposición de datos frecuentes, pero NO garantiza eliminar el 100% de los datos
sensibles posibles en texto libre.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Tuple
from urllib.parse import urlsplit, urlunsplit

from scripts.url_analyzer import extract_urls


# Expresiones regulares para patrones sensibles comunes
CBU_CVU_REGEX = re.compile(r"\b\d{22}\b")
CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
CUIT_CUIL_REGEX = re.compile(r"\b(?:20|23|24|27|30|33|34)-\d{8}-\d\b")
DNI_REGEX = re.compile(r"(?i)\b(?:dni|documento)\s*[:#º°]?\s*(\d{1,2}\.?\d{3}\.?\d{3}|\d{7,8})\b")
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_REGEX = re.compile(r"(?:\+?54\s*9?\s*)?(?:\(?0?\d{2,4}\)?[\s-]*)?\d{3,4}[\s-]+\d{4}\b")
URL_SENSITIVE_PARAM_REGEX = re.compile(
    r"(?i)((?:token|pass|password|clave|pin|otp|dni|cuit|cuil|cbu|cvu|email|correo|session|key|secret)=)([^&#\s]+)"
)


def sanitize_url_for_external_llm(url: str) -> Tuple[str, bool]:
    """
    Oculta credenciales embebidas (`user:pass@host`) y parámetros o valores sensibles
    en una URL antes de enviarla al modelo externo, conservando el esquema, dominio y ruta base.
    El enlace original se mantiene intacto en memoria local para `url_analyzer`.
    """
    if not url:
        return "", False

    changed = False
    working = url
    try:
        parts = urlsplit(working if "://" in working else f"http://{working}")
        has_scheme = "://" in working
        netloc = parts.netloc
        if "@" in netloc:
            _, _, hostpart = netloc.rpartition("@")
            netloc = f"[CREDENCIAL_URL_OCULTA]@{hostpart}"
            changed = True

        path = parts.path
        if CBU_CVU_REGEX.search(path):
            path = CBU_CVU_REGEX.sub("[CBU_CVU_OCULTO]", path)
            changed = True
        if EMAIL_REGEX.search(path):
            path = EMAIL_REGEX.sub("[EMAIL_OCULTO]", path)
            changed = True

        query = parts.query
        if query:
            if URL_SENSITIVE_PARAM_REGEX.search(query):
                query = URL_SENSITIVE_PARAM_REGEX.sub(r"\1[VALOR_URL_OCULTO]", query)
                changed = True
            if EMAIL_REGEX.search(query):
                query = EMAIL_REGEX.sub("[EMAIL_OCULTO]", query)
                changed = True
            if CBU_CVU_REGEX.search(query):
                query = CBU_CVU_REGEX.sub("[CBU_CVU_OCULTO]", query)
                changed = True

        rebuilt = urlunsplit((parts.scheme if has_scheme else "", netloc, path, query, parts.fragment))
        if not has_scheme and rebuilt.startswith("//"):
            rebuilt = rebuilt[2:]
        return rebuilt, changed
    except Exception:
        return working, False


@dataclass
class SanitizationReport:
    """Resumen transparente de qué se enmascaró antes de enviar al proveedor externo."""
    masked_text: str
    redactions_count: int = 0
    redacted_categories: List[str] = field(default_factory=list)
    sent_char_count: int = 0
    provider_name: str = "Google Gemini API"
    disclaimer: str = (
        "Se enviaron al proveedor externo únicamente metadatos de control y el texto con "
        "ocultamiento preventivo de patrones numéricos/personales comunes (CBU/CVU, tarjetas, "
        "CUIT/DNI, correos y teléfonos). Las imágenes nunca se envían a la API (se procesan con "
        "Tesseract OCR local). Importante: el ocultamiento automático reduce la exposición, pero "
        "no garantiza eliminar todos los datos sensibles que pudieran escribirse en texto libre."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "sent_char_count": self.sent_char_count,
            "redactions_count": self.redactions_count,
            "redacted_categories": list(self.redacted_categories),
            "masked_preview": (
                self.masked_text[:280] + ("..." if len(self.masked_text) > 280 else "")
            ),
            "disclaimer": self.disclaimer,
        }


def sanitize_text_for_external_llm(
    text: str,
    provider_name: str = "Google Gemini API",
) -> SanitizationReport:
    """
    Oculta datos personales/financieros obvios preservando las URLs del mensaje
    para que los agentes no pierdan visibilidad sobre los enlaces sospechosos.
    """
    if not text:
        return SanitizationReport(
            masked_text="",
            redactions_count=0,
            redacted_categories=[],
            sent_char_count=0,
            provider_name=provider_name,
        )

    # 1. Proteger temporalmente las URLs para no alterar dominios o rutas con números
    urls = extract_urls(text)
    url_placeholders: Dict[str, str] = {}
    working = text
    for idx, url in enumerate(urls):
        token = f"__URL_PLACEHOLDER_{idx}__"
        url_placeholders[token] = url
        working = working.replace(url, token)

    redactions = 0
    categories: List[str] = []

    def _apply_mask(pattern: re.Pattern, replacement: str, category_label: str, current: str) -> str:
        nonlocal redactions
        matches = list(pattern.finditer(current))
        if matches:
            redactions += len(matches)
            if category_label not in categories:
                categories.append(category_label)
            return pattern.sub(replacement, current)
        return current

    # Orden de especificidad: CBU/CVU (22 dígitos) -> CUIT/CUIL -> Tarjetas -> DNI -> Email -> Teléfonos
    working = _apply_mask(CBU_CVU_REGEX, "[CBU_CVU_OCULTO]", "CBU/CVU", working)
    working = _apply_mask(CUIT_CUIL_REGEX, "[CUIT_OCULTO]", "CUIT/CUIL", working)
    working = _apply_mask(CARD_REGEX, "[TARJETA_OCULTA]", "Tarjeta bancaria", working)
    working = _apply_mask(DNI_REGEX, "DNI [DNI_OCULTO]", "DNI", working)
    working = _apply_mask(EMAIL_REGEX, "[EMAIL_OCULTO]", "Correo electrónico", working)
    working = _apply_mask(PHONE_REGEX, "[TELEFONO_OCULTO]", "Teléfono", working)

    # Restaurar las URLs con sanitización preventiva de credenciales o parámetros sensibles
    for token, original_url in url_placeholders.items():
        safe_url, url_redacted = sanitize_url_for_external_llm(original_url)
        if url_redacted:
            redactions += 1
            if "Credenciales/Parámetros en URL" not in categories:
                categories.append("Credenciales/Parámetros en URL")
        working = working.replace(token, safe_url)

    return SanitizationReport(
        masked_text=working,
        redactions_count=redactions,
        redacted_categories=categories,
        sent_char_count=len(working),
        provider_name=provider_name,
    )


def sanitize_snippets_for_external_llm(snippets: List[str]) -> List[str]:
    """
    Aplica enmascaramiento preventivo de PII a fragmentos de evidencia antes de
    incluirlos en la respuesta de una herramienta que vuelve al modelo externo.
    """
    return [sanitize_text_for_external_llm(s).masked_text for s in (snippets or [])]

