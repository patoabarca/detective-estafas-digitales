"""
Módulo de Procesamiento y Validación Segura de Imágenes en Memoria.

Principios de Seguridad y Robustez:
- Validación real por cabecera binaria (magic bytes e Image.format), nunca solo por extensión.
- Protección estricta contra ataques de descompresión (Decompression Bombs / DoS).
- Procesamiento 100% en memoria (RAM / BytesIO), sin almacenar archivos temporales en disco.
- Eliminación de metadatos EXIF / perfiles no necesarios para el análisis de texto.
- Preprocesamiento óptico (escala de grises, contraste adaptativo) para optimizar la legibilidad en OCR.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, Set, Tuple

from PIL import Image, ImageEnhance, ImageOps

# Límites defensivos de seguridad
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB máximo
MAX_ALLOWED_PIXELS = 25_000_000         # 25 Megapíxeles (evita Decompression Bombs)
MAX_DIMENSION = 5000                    # Ancho o alto máximo en píxeles
ALLOWED_PIL_FORMATS: Set[str] = {"PNG", "JPEG", "WEBP"}
ALLOWED_EXTENSIONS: Set[str] = {".png", ".jpg", ".jpeg", ".webp"}

# Configurar Pillow para prevenir bombas de descompresión
Image.MAX_IMAGE_PIXELS = MAX_ALLOWED_PIXELS


class ImageValidationError(ValueError):
    """Excepción lanzada cuando una imagen no supera los controles de integridad o seguridad."""
    pass


def validate_and_load_image(
    file_bytes: bytes,
    original_filename: str = "",
) -> Image.Image:
    """
    Valida e inicializa una imagen a partir de un flujo de bytes en memoria.

    Controles realizados:
    1. Límite de tamaño en bytes.
    2. Comprobación de extensión orientativa (si se suministra).
    3. Inspección de cabecera binaria y validación del formato real mediante Pillow.
    4. Comprobación de resolución y límites de píxeles para mitigar ataques DoS.
    5. Conversión a modo estándar RGB y descarte de metadatos EXIF / scripts embebidos.

    Retorna:
        PIL.Image.Image: Objeto de imagen en memoria sanitizado y listo para visualización u OCR.
    """
    if not file_bytes:
        raise ImageValidationError("El archivo proporcionado está vacío o no contiene bytes válidos.")

    # 1. Comprobación de tamaño en bytes
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        size_mb = len(file_bytes) / (1024 * 1024)
        raise ImageValidationError(
            f"El archivo ({size_mb:.2f} MB) excede el tamaño máximo permitido de {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
        )

    # 2. Comprobación opcional de extensión
    if original_filename:
        ext = Path(original_filename).suffix.lower()
        if ext and ext not in ALLOWED_EXTENSIONS:
            raise ImageValidationError(
                f"La extensión '{ext}' no está permitida. Formatos admitidos: PNG, JPG, JPEG, WEBP."
            )

    # 3. Apertura e inspección binaria en memoria
    byte_stream = io.BytesIO(file_bytes)
    try:
        raw_img = Image.open(byte_stream)
        raw_img.verify()  # Verifica integridad estructural del archivo
    except Exception as exc:
        raise ImageValidationError(
            f"El archivo no es una imagen válida o se encuentra corrupto: {str(exc)}"
        )

    # Reabrir el flujo tras verify() (verify invalida el descriptor interno)
    byte_stream.seek(0)
    try:
        img = Image.open(byte_stream)
    except Exception as exc:
        raise ImageValidationError(f"No fue posible cargar la imagen verificada: {str(exc)}")

    # 4. Verificación del formato real reportado por Pillow
    if img.format not in ALLOWED_PIL_FORMATS:
        raise ImageValidationError(
            f"Formato de imagen no permitido: '{img.format}'. Formatos autorizados: {', '.join(ALLOWED_PIL_FORMATS)}."
        )

    # 5. Verificación de dimensiones
    width, height = img.size
    total_pixels = width * height

    if width < 10 or height < 10:
        raise ImageValidationError(
            f"Dimensiones de imagen demasiado pequeñas ({width}x{height} px) para contener texto legible."
        )

    if width > MAX_DIMENSION or height > MAX_DIMENSION or total_pixels > MAX_ALLOWED_PIXELS:
        raise ImageValidationError(
            f"Dimensiones de imagen excesivas ({width}x{height} px, {total_pixels} píxeles). "
            f"El límite máximo de seguridad es {MAX_DIMENSION}x{MAX_DIMENSION} px."
        )

    # 6. Crear una copia en memoria completamente aislada y sanitizada (modo RGB)
    # Esto descarta metadatos EXIF, comentarios o perfiles ICC no seguros
    sanitized = Image.new("RGB", (width, height), (255, 255, 255))
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        # Manejo adecuado de canal alfa sobre fondo blanco
        sanitized.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[3])
    else:
        sanitized.paste(img.convert("RGB"))

    return sanitized


def preprocess_image_for_ocr(
    image: Image.Image,
    target_dpi_factor: float = 1.0,
) -> Image.Image:
    """
    Preprocesa una imagen para maximizar la tasa de acierto del motor de OCR.

    Transformaciones aplicadas:
    - Re-escalado adaptativo: si la imagen es una captura pequeña o mediana (resolución
      típica de pantalla 72-96 DPI), se escala 2x para alcanzar la altura en píxeles óptima
      requerida por los modelos LSTM de Tesseract. Si es excesivamente grande, se reduce para
      mantener tiempos de respuesta ágiles.
    - Conversión a escala de grises.
    - Normalización de contraste y realce de definición para destacar el texto sobre fondos
      claros u oscuros frecuentes en WhatsApp, clientes de correo o navegadores.
    """
    w, h = image.size
    max_side = 2500

    # Re-escalado adaptativo según resolución inicial
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        new_size = (int(w * scale), int(h * scale))
        processed = image.resize(new_size, Image.Resampling.LANCZOS)
    elif max(w, h) < 1800:
        # Captura de pantalla de resolución estándar: escalar para elevar DPI relativo
        scale = min(2.0, max_side / max(w, h))
        new_size = (int(w * scale), int(h * scale))
        processed = image.resize(new_size, Image.Resampling.LANCZOS)
    else:
        processed = image.copy()

    # 1. Convertir a escala de grises
    gray = processed.convert("L")

    # 2. Ajuste automático de contraste (autocontrast)
    try:
        contrasted = ImageOps.autocontrast(gray, cutoff=1)
    except Exception:
        contrasted = gray

    # 3. Realce de contraste ligero para texto tenue
    enhancer = ImageEnhance.Contrast(contrasted)
    enhanced = enhancer.enhance(1.5)

    return enhanced

