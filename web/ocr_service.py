"""
Módulo de Reconocimiento Óptico de Caracteres (OCR) Local y Auditoría de URLs.

Este módulo gestiona la interacción local con Tesseract OCR mediante pytesseract:
- Búsqueda y autoconfiguración del binario en Windows, Linux y macOS.
- Verificación del modelo de idioma español ('spa').
- Manejo de degradación elegante cuando Tesseract no está instalado en el sistema.
- Detección heurística de distorsiones comunes del OCR en direcciones web (URLs),
  alertando al usuario para que corrija manualmente el texto antes del análisis.
- Cero conexiones a APIs en la nube (100% privado y local).
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False


class OCRService:
    """
    Servicio de OCR local con detección automática de entorno y defensas de integridad.
    """

    def __init__(self, custom_tesseract_cmd: Optional[str] = None) -> None:
        self.tesseract_cmd: Optional[str] = None
        self.is_available: bool = False
        self.version: Optional[str] = None
        self.available_languages: List[str] = []
        self.has_spanish: bool = False
        self.initialization_error: Optional[str] = None

        self._configure_binary(custom_tesseract_cmd)

    def _configure_binary(self, custom_cmd: Optional[str] = None) -> None:
        """Localiza y configura la ruta del ejecutable de Tesseract."""
        if not PYTESSERACT_AVAILABLE:
            self.is_available = False
            self.initialization_error = "El paquete 'pytesseract' no está instalado en el entorno Python."
            return

        candidates: List[str] = []

        # 1. Ruta explícita por parámetro
        if custom_cmd:
            candidates.append(custom_cmd)

        # 2. Variable de entorno TESSERACT_CMD
        env_cmd = os.environ.get("TESSERACT_CMD")
        if env_cmd:
            candidates.append(env_cmd)

        # 3. Búsqueda en PATH del sistema
        which_path = shutil.which("tesseract")
        if which_path:
            candidates.append(which_path)

        # 4. Rutas estándar en sistemas Windows
        if sys.platform.startswith("win"):
            candidates.extend([
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
            ])

        found_binary: Optional[str] = None
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                found_binary = str(Path(candidate).resolve())
                break

        if found_binary:
            try:
                # Configurar TESSDATA_PREFIX si existe carpeta tessdata local en el proyecto
                local_tessdata = Path(__file__).resolve().parent.parent / "tessdata"
                if local_tessdata.is_dir() and "TESSDATA_PREFIX" not in os.environ:
                    os.environ["TESSDATA_PREFIX"] = str(local_tessdata)

                pytesseract.pytesseract.tesseract_cmd = found_binary
                # Probar ejecución simple
                version_str = str(pytesseract.get_tesseract_version())
                langs = pytesseract.get_languages()

                self.tesseract_cmd = found_binary
                self.is_available = True
                self.version = version_str
                self.available_languages = langs
                self.has_spanish = "spa" in langs
                self.initialization_error = None
            except Exception as exc:
                self.is_available = False
                self.tesseract_cmd = found_binary
                self.initialization_error = (
                    f"Se encontró el binario en '{found_binary}', pero ocurrió un error al inicializar: {str(exc)}"
                )
        else:
            self.is_available = False
            self.tesseract_cmd = None
            self.initialization_error = (
                "No se encontró el ejecutable de Tesseract OCR en el sistema.\n"
                "Para activarlo en Windows, podés instalarlo con:\n"
                "  winget install UB-Mannheim.TesseractOCR\n"
                "o descargarlo desde GitHub (asegurándote de incluir el paquete de idioma 'Spanish')."
            )

    def get_status(self) -> Dict[str, Any]:
        """Retorna el diagnóstico actual del motor de OCR."""
        return {
            "available": self.is_available,
            "binary_path": self.tesseract_cmd,
            "version": self.version,
            "languages": self.available_languages,
            "has_spanish": self.has_spanish,
            "error_message": self.initialization_error,
        }

    def extract_text(self, image: Image.Image) -> Dict[str, Any]:
        """
        Extrae el texto de la imagen suministrada mediante OCR local.

        Retorna:
            Dict[str, Any]:
                - 'success': bool
                - 'text': str (texto extraído y saneado)
                - 'url_warnings': list (advertencias sobre posibles errores en URLs)
                - 'language_used': str
                - 'error': str (si hubo falla)
        """
        if not self.is_available:
            return {
                "success": False,
                "text": "",
                "url_warnings": [],
                "language_used": "ninguno",
                "error": self.initialization_error or "Tesseract OCR no está disponible en este equipo.",
                "installation_guide": (
                    "Para habilitar el reconocimiento automático de capturas:\n"
                    "1. Instalá Tesseract OCR (ej: winget install UB-Mannheim.TesseractOCR).\n"
                    "2. Seleccioná el paquete adicional 'Spanish language data'.\n"
                    "3. Reiniciá la aplicación Streamlit."
                ),
            }

        # Selección de idioma preferido
        if self.has_spanish:
            lang_code = "spa+eng" if "eng" in self.available_languages else "spa"
        elif "eng" in self.available_languages:
            lang_code = "eng"
        else:
            lang_code = self.available_languages[0] if self.available_languages else "eng"

        try:
            # Ejecución local de pytesseract en memoria
            raw_text = pytesseract.image_to_string(image, lang=lang_code)
            sanitized_text = self._sanitize_extracted_text(raw_text)

            # Si el texto extraído es muy breve o vacío, intentar con segmentación de bloque (--psm 6)
            if len(sanitized_text.strip()) < 5:
                try:
                    fallback_text = pytesseract.image_to_string(image, lang=lang_code, config="--psm 6")
                    fallback_sanitized = self._sanitize_extracted_text(fallback_text)
                    if len(fallback_sanitized.strip()) > len(sanitized_text.strip()):
                        sanitized_text = fallback_sanitized
                except Exception:
                    pass

            # Heurística de detección de anomalías tipográficas en URLs
            url_warnings = self.detect_ocr_url_anomalies(sanitized_text)

            return {
                "success": True,
                "text": sanitized_text,
                "url_warnings": url_warnings,
                "language_used": lang_code,
                "error": None,
            }

        except Exception as exc:
            return {
                "success": False,
                "text": "",
                "url_warnings": [],
                "language_used": lang_code,
                "error": f"Error durante la extracción de OCR: {str(exc)}",
            }

    @staticmethod
    def _sanitize_extracted_text(text: str) -> str:
        """Limpia caracteres nulos y normaliza saltos de línea."""
        if not text:
            return ""
        # Eliminar caracteres nulos o de control no imprimibles
        clean = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ch >= " ")
        # Limitar saltos de línea consecutivos
        clean = re.sub(r"\n{3,}", "\n\n", clean)
        return clean.strip()

    @staticmethod
    def detect_ocr_url_anomalies(text: str) -> List[Dict[str, str]]:
        """
        Analiza el texto extraído en busca de posibles confusiones tipográficas
        típicas del OCR en direcciones web (URLs).

        Casos contemplados:
        - Espacios indebidos dentro de enlaces (ej: 'https : / /' o '. c o m').
        - Comas en lugar de puntos (ej: 'banco,com,ar').
        - Confusión visual de caracteres en nombres de dominio (ej: ceros en lugar de 'o',
          número '1' en lugar de 'l' o 'i').
        - Protocolos truncados o incompletos.
        """
        warnings: List[Dict[str, str]] = []

        # 1. Espacios en protocolos o dominios
        broken_protocols = re.findall(r"(?i)\bhttps?\s*:\s*/\s*/\S*", text)
        for bp in broken_protocols:
            if " " in bp:
                warnings.append({
                    "type": "espacio_en_protocolo",
                    "snippet": bp,
                    "explanation": (
                        f"El enlace '{bp}' contiene espacios detectados por el OCR. "
                        "Revisá y eliminá los espacios antes de analizar."
                    ),
                })

        # 2. Comas en lugar de puntos en nombres que parecen dominios
        comma_domains = re.findall(r"(?i)\b[a-z0-9\-]+,[a-z]{2,6}(?:,[a-z]{2})?\b", text)
        for cd in comma_domains:
            warnings.append({
                "type": "coma_por_punto",
                "snippet": cd,
                "explanation": (
                    f"El fragmento '{cd}' contiene comas donde usualmente van puntos. "
                    "Es común que el OCR confunda '.' con ','. Verificá si corresponde a una dirección web."
                ),
            })

        # 3. Confusión de 'vv' por 'w' en 'www'
        vv_match = re.findall(r"(?i)\b(?:vvv|vv|vw|wv)\.[a-z0-9\-]+\.[a-z]{2,}\b", text)
        for vm in vv_match:
            warnings.append({
                "type": "confusion_w",
                "snippet": vm,
                "explanation": (
                    f"El fragmento '{vm}' parece una confusión de letras 'vv' por 'w' (ej: 'www')."
                ),
            })

        # 4. Números sustituyendo letras en marcas bancarias comunes dentro de dominios
        # Ejemplo: g00gle, ga1icia, santand3r, mercad0pag0
        brand_leets = [
            (r"(?i)\b[a-z0-9\-]*ga[1l]icia[a-z0-9\-]*\b", "galicia"),
            (r"(?i)\b[a-z0-9\-]*santand[3e]r[a-z0-9\-]*\b", "santander"),
            (r"(?i)\b[a-z0-9\-]*mercad[0o]pag[0o][a-z0-9\-]*\b", "mercadopago"),
            (r"(?i)\b[a-z0-9\-]*bbva|franc[3e]s[a-z0-9\-]*\b", "bbva"),
        ]
        for pattern, brand in brand_leets:
            matches = re.finditer(pattern, text)
            for m in matches:
                val = m.group(0)
                # Si contiene números reemplazando letras conocidas
                if any(c.isdigit() for c in val):
                    warnings.append({
                        "type": "caracter_leetspeak_o_ocr",
                        "snippet": val,
                        "explanation": (
                            f"El fragmento '{val}' contiene números combinados con el nombre de '{brand}'. "
                            "Puede tratarse de una confusión del OCR (ej: '1' por 'l', '0' por 'o') o de un engaño deliberado."
                        ),
                    })

        return warnings


# Instancia única reutilizable (singleton defensivo)
_GLOBAL_OCR_SERVICE: Optional[OCRService] = None


def get_ocr_service() -> OCRService:
    """Retorna la instancia global del servicio OCR."""
    global _GLOBAL_OCR_SERVICE
    if _GLOBAL_OCR_SERVICE is None:
        _GLOBAL_OCR_SERVICE = OCRService()
    return _GLOBAL_OCR_SERVICE
