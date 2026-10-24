"""
Pruebas de Seguridad y Validación de Entradas de la Aplicación Web (web/image_processor.py).
"""

import io
import pytest
from PIL import Image
from web.image_processor import (
    ImageValidationError,
    preprocess_image_for_ocr,
    validate_and_load_image,
)


class TestWebSecurityAndImages:
    """Pruebas de seguridad contra ataques de descompresión, formatos maliciosos y corrupción."""

    @staticmethod
    def _create_sample_image_bytes(format="PNG", size=(100, 100), color="white") -> bytes:
        img = Image.new("RGB", size, color=color)
        buf = io.BytesIO()
        img.save(buf, format=format)
        return buf.getvalue()

    def test_valid_png_image_accepted(self):
        b = self._create_sample_image_bytes("PNG")
        loaded = validate_and_load_image(b, "captura.png")

        assert isinstance(loaded, Image.Image)
        assert loaded.size == (100, 100)

    def test_valid_jpeg_image_accepted(self):
        b = self._create_sample_image_bytes("JPEG")
        loaded = validate_and_load_image(b, "captura.jpg")

        assert isinstance(loaded, Image.Image)
        assert loaded.size == (100, 100)

    def test_valid_webp_image_accepted(self):
        b = self._create_sample_image_bytes("WEBP")
        loaded = validate_and_load_image(b, "captura.webp")

        assert isinstance(loaded, Image.Image)
        assert loaded.size == (100, 100)

    def test_empty_bytes_rejected(self):
        with pytest.raises(ImageValidationError, match="vacío"):
            validate_and_load_image(b"", "vacio.png")

    def test_corrupted_bytes_rejected(self):
        corrupt = b"ESTO_NO_ES_UNA_IMAGEN_SINO_UN_TEXTO_ALEATORIO"
        with pytest.raises(ImageValidationError, match="no es una imagen válida"):
            validate_and_load_image(corrupt, "corrupto.png")

    def test_disallowed_extension_rejected(self):
        b = self._create_sample_image_bytes("PNG")
        with pytest.raises(ImageValidationError, match="no está permitida"):
            validate_and_load_image(b, "script.exe")

    def test_fake_extension_magic_bytes_checked(self):
        # Un archivo de texto disfrazado con extensión .png
        fake_png = b"Payload malicioso en texto plano"
        with pytest.raises(ImageValidationError, match="no es una imagen válida"):
            validate_and_load_image(fake_png, "trampa.png")

    def test_tiny_image_rejected(self):
        tiny_b = self._create_sample_image_bytes("PNG", size=(5, 5))
        with pytest.raises(ImageValidationError, match="demasiado pequeñas"):
            validate_and_load_image(tiny_b, "chica.png")

    def test_oversized_file_size_rejected(self):
        # Simular payload mayor al límite de 10 MB
        oversized = b"A" * (11 * 1024 * 1024)
        with pytest.raises(ImageValidationError, match="excede el tamaño máximo"):
            validate_and_load_image(oversized, "gigante.png")

    def test_preprocessing_contrast_enhancement(self):
        b = self._create_sample_image_bytes("PNG", size=(300, 150), color="gray")
        img = validate_and_load_image(b, "test.png")
        processed = preprocess_image_for_ocr(img)

        assert isinstance(processed, Image.Image)
        assert processed.mode == "L"  # Escala de grises
        # Verifica escalado adaptativo 2x para capturas de baja resolución
        assert processed.size == (600, 300)

