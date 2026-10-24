"""
Pruebas del Módulo de OCR Local y Heurísticas de URLs (web/ocr_service.py).
"""

from unittest.mock import MagicMock, patch
import pytest
from PIL import Image
from web.ocr_service import OCRService, get_ocr_service


class TestOCRService:
    """Pruebas unitarias para el servicio de OCR y sus heurísticas."""

    def test_singleton_instance(self):
        service1 = get_ocr_service()
        service2 = get_ocr_service()
        assert service1 is service2

    def test_ocr_status_structure(self):
        service = OCRService()
        status = service.get_status()

        assert "available" in status
        assert "binary_path" in status
        assert "languages" in status
        assert "has_spanish" in status
        assert "error_message" in status

    def test_sanitize_extracted_text(self):
        raw = "Hola\x00mundo\x07!\n\n\n\nPrueba de texto."
        cleaned = OCRService._sanitize_extracted_text(raw)

        assert "\x00" not in cleaned
        assert "\x07" not in cleaned
        assert "\n\n\n\n" not in cleaned
        assert "Hola mundo!" in cleaned or "Holamundo!" in cleaned
        assert "Prueba de texto." in cleaned

    def test_detect_url_anomalies_spaces(self):
        text = "Por favor ingrese a https : / / galicia-segura.com para validar."
        warnings = OCRService.detect_ocr_url_anomalies(text)

        assert len(warnings) >= 1
        assert any(w["type"] == "espacio_en_protocolo" for w in warnings)

    def test_detect_url_anomalies_commas(self):
        text = "Acceda inmediatamente a banco,com,ar y confirme sus datos."
        warnings = OCRService.detect_ocr_url_anomalies(text)

        assert len(warnings) >= 1
        assert any(w["type"] == "coma_por_punto" for w in warnings)

    def test_detect_url_anomalies_vv(self):
        text = "Visite vv.bancogalicia.com para más información."
        warnings = OCRService.detect_ocr_url_anomalies(text)

        assert len(warnings) >= 1
        assert any(w["type"] == "confusion_w" for w in warnings)

    def test_detect_url_anomalies_leetspeak_digits(self):
        text = "Ingrese a https://ga1icia-online.com o a http://mercad0pag0-login.com hoy."
        warnings = OCRService.detect_ocr_url_anomalies(text)

        assert len(warnings) >= 1
        assert any(w["type"] == "caracter_leetspeak_o_ocr" for w in warnings)

    def test_extract_text_when_tesseract_unavailable(self):
        service = OCRService()
        service.is_available = False
        service.initialization_error = "Tesseract no encontrado"

        img = Image.new("RGB", (100, 100), color="white")
        res = service.extract_text(img)

        assert res["success"] is False
        assert "installation_guide" in res
        assert res["text"] == ""

    def test_extract_text_mocked_success(self):
        service = OCRService()
        service.is_available = True
        service.has_spanish = True
        service.available_languages = ["spa", "eng"]

        img = Image.new("RGB", (200, 50), color="white")

        with patch("pytesseract.image_to_string", return_value="Su cuenta bancaria será suspendida hoy."):
            res = service.extract_text(img)

            assert res["success"] is True
            assert "cuenta bancaria" in res["text"]
            assert res["error"] is None

    def test_extract_text_mocked_error(self):
        service = OCRService()
        service.is_available = True
        service.has_spanish = False
        service.available_languages = ["eng"]

        img = Image.new("RGB", (100, 100), color="white")

        with patch("pytesseract.image_to_string", side_effect=RuntimeError("Memoria insuficiente")):
            res = service.extract_text(img)

            assert res["success"] is False
            assert "Error durante la extracción" in res["error"]
