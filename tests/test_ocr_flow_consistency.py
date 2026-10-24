"""
Pruebas de Regresión y Consistencia del Flujo OCR vs. Texto Directo.

Verifica que el motor determinístico produzca exactamente la misma clasificación
y puntuación independientemente de si el texto ingresó por:
1. Llamada directa a scripts/worker.py (run_pipeline).
2. Adaptador web con modalidad 'text' (pestaña Pegar Texto).
3. Adaptador web con modalidad 'ocr_screenshot' (pestaña Subir Captura).
4. Extracción real con Tesseract OCR sobre una imagen sintética en memoria.

Además valida:
- Invarianza ante saltos de línea, espacios no separables (\\u00a0) y formas Unicode.
- Integridad de la telemetría de diagnóstico (hash SHA-256 sin PII).
"""

import hashlib
import io
import unicodedata
import pytest
from PIL import Image, ImageDraw

from scripts.worker import run_pipeline, load_policy
from web.analysis_adapter import (
    analyze_text,
    normalize_text_content,
    create_diagnostic_entry,
)
from web.ocr_service import get_ocr_service


# Mensaje sintético inspirado en el correo electrónico de la auditoría
SYNTHETIC_EMAIL_PHISHING = (
    "Estimado usuario: Esta es la última vez que te informamos que dejaremos de "
    "procesar los correos electrónicos que llegan a tu cuenta porque no has podido "
    "verificarla, lo que podría provocar la eliminación definitiva de tu cuenta en las "
    "próximas horas. Por favor, completá nuestra verificación de seguridad. "
    "VERIFICAR LA ACTUALIZACIÓN"
)


class TestOCRFlowConsistency:
    """Suite de consistencia y regresión entre flujos de entrada."""

    def test_direct_pipeline_evaluation(self):
        """1. Entrada directa del texto al motor (run_pipeline)."""
        policy = load_policy()
        report = run_pipeline(SYNTHETIC_EMAIL_PHISHING, policy)

        assert report["status"] == "success"
        risk = report["risk_assessment"]
        assert risk["level"] == "ALTO"
        assert risk["score"] >= 80

        # Reglas esperadas activadas
        rule_prefixes = [r.split()[0].strip() for r in risk["activated_rules"]]
        assert "REGLA-ING-01" in rule_prefixes  # Amenaza de eliminación / bloqueo
        assert "REGLA-ING-02" in rule_prefixes  # Urgencia artificial (última vez / próximas horas)
        assert "REGLA-FRA-01" in rule_prefixes  # Solicitud de verificación de seguridad

    def test_web_adapter_text_mode_evaluation(self):
        """2. Entrada del mismo texto mediante el adaptador web (modalidad texto)."""
        report = analyze_text(SYNTHETIC_EMAIL_PHISHING, input_mode="text")

        assert report["status"] == "success"
        assert report["input_mode"] == "text"
        assert report["risk_assessment"]["level"] == "ALTO"
        assert report["risk_assessment"]["score"] >= 80

    def test_web_adapter_ocr_mode_evaluation(self):
        """3. Entrada del mismo texto mediante el adaptador web (modalidad OCR)."""
        report = analyze_text(SYNTHETIC_EMAIL_PHISHING, input_mode="ocr_screenshot")

        assert report["status"] == "success"
        assert report["input_mode"] == "ocr_screenshot"
        assert report["risk_assessment"]["level"] == "ALTO"
        assert report["risk_assessment"]["score"] >= 80

    def test_strict_deterministic_equality_across_modes(self):
        """4. Comparación de puntajes, categorías y reglas entre modalidades."""
        report_direct = run_pipeline(SYNTHETIC_EMAIL_PHISHING)
        report_text = analyze_text(SYNTHETIC_EMAIL_PHISHING, input_mode="text")
        report_ocr = analyze_text(SYNTHETIC_EMAIL_PHISHING, input_mode="ocr_screenshot")

        # Puntajes idénticos
        assert report_direct["risk_assessment"]["score"] == report_text["risk_assessment"]["score"]
        assert report_text["risk_assessment"]["score"] == report_ocr["risk_assessment"]["score"]

        # Niveles de riesgo idénticos
        assert report_direct["risk_assessment"]["level"] == report_text["risk_assessment"]["level"]
        assert report_text["risk_assessment"]["level"] == report_ocr["risk_assessment"]["level"]

        # Reglas activadas idénticas
        assert report_direct["risk_assessment"]["activated_rules"] == report_text["risk_assessment"]["activated_rules"]
        assert report_text["risk_assessment"]["activated_rules"] == report_ocr["risk_assessment"]["activated_rules"]

        # Indicadores detectados idénticos
        assert len(report_direct["indicators_detected"]) == len(report_text["indicators_detected"])
        assert len(report_text["indicators_detected"]) == len(report_ocr["indicators_detected"])

    def test_invariance_under_ocr_whitespace_and_newlines(self):
        """
        5. Comparación con variaciones típicas introducidas por el OCR:
        - Múltiples saltos de línea (\\n) por división de renglones en la imagen.
        - Espacios no separables (\\u00a0).
        - Espacios múltiples.
        """
        ocr_variant = (
            "Estimado usuario:\n\n"
            "Esta es la última vez que te informamos que dejaremos de\n"
            "procesar los correos electrónicos que llegan a tu cuenta\n"
            "porque no has podido verificarla, lo que podría provocar la\n"
            "eliminación definitiva de tu cuenta en las próximas horas.\n\n"
            "Por favor,\u00a0completá nuestra verificación de seguridad.\n\n"
            "VERIFICAR  LA  ACTUALIZACIÓN"
        )

        report_original = analyze_text(SYNTHETIC_EMAIL_PHISHING, input_mode="text")
        report_variant = analyze_text(ocr_variant, input_mode="ocr_screenshot")

        assert report_variant["risk_assessment"]["level"] == report_original["risk_assessment"]["level"]
        assert report_variant["risk_assessment"]["score"] == report_original["risk_assessment"]["score"]
        assert (
            report_variant["risk_assessment"]["activated_rules"]
            == report_original["risk_assessment"]["activated_rules"]
        )

    def test_real_tesseract_ocr_on_synthetic_image(self):
        """
        6. Ejecución real de Tesseract OCR sobre una imagen sintética en memoria.
        Genera la imagen con Pillow, extrae el texto con OCRService y verifica
        que el análisis sobre el texto reconocido arroje RIESGO ALTO.
        """
        ocr_service = get_ocr_service()
        if not ocr_service.is_available:
            pytest.skip("Tesseract OCR no está disponible en este entorno.")

        # Generar imagen sintética legible en memoria
        img_w, img_h = 950, 320
        image = Image.new("RGB", (img_w, img_h), color="white")
        draw = ImageDraw.Draw(image)

        lines = [
            "Estimado usuario: Esta es la ultima vez que te informamos",
            "que dejaremos de procesar los correos electronicos que llegan a tu cuenta",
            "porque no has podido verificarla, lo que podria provocar",
            "la eliminacion definitiva de tu cuenta en las proximas horas.",
            "Por favor, completa nuestra verificacion de seguridad.",
            "VERIFICAR LA ACTUALIZACION",
        ]
        y_offset = 20
        for line in lines:
            draw.text((25, y_offset), line, fill="black")
            y_offset += 45

        # Extracción real mediante Tesseract
        ocr_result = ocr_service.extract_text(image)
        assert ocr_result["success"] is True
        extracted_text = ocr_result["text"]
        assert len(extracted_text) > 50

        # Análisis a través del adaptador en modalidad OCR
        report_from_ocr = analyze_text(extracted_text, input_mode="ocr_screenshot")
        assert report_from_ocr["status"] == "success"
        assert report_from_ocr["risk_assessment"]["level"] in ("ALTO", "CRITICO")
        assert report_from_ocr["risk_assessment"]["score"] >= 50

    def test_diagnostic_telemetry_generation(self):
        """7. Verificación de la telemetría de diagnóstico segura (SHA-256, sin PII)."""
        report = analyze_text(
            SYNTHETIC_EMAIL_PHISHING,
            input_mode="ocr_screenshot",
            enable_diagnostics=True,
        )

        assert "diagnostic_telemetry" in report
        diag = report["diagnostic_telemetry"]

        assert diag["flow_name"] == "ocr_screenshot"
        assert diag["char_count"] == len(normalize_text_content(SYNTHETIC_EMAIL_PHISHING))
        assert diag["risk_level"] == "ALTO"
        assert diag["score"] >= 80

        # El hash SHA-256 debe coincidir con el hash del texto normalizado
        expected_hash = hashlib.sha256(
            normalize_text_content(SYNTHETIC_EMAIL_PHISHING).encode("utf-8")
        ).hexdigest()
        assert diag["sha256_hash"] == expected_hash

        # No debe contener texto plano del mensaje ni datos personales
        assert "Estimado usuario" not in str(diag)

    def test_unicode_normalization_function(self):
        """8. Prueba unitaria de la función normalize_text_content."""
        # Texto con zero-width spaces, non-breaking space y CRLF
        tricky = "Hola\u200b\u00a0mundo\r\n\r\nPrueba\ufeffde\u202ftexto."
        clean = normalize_text_content(tricky)

        assert "\u200b" not in clean
        assert "\ufeff" not in clean
        assert "\u00a0" not in clean
        assert "\u202f" not in clean
        assert "\r\n" not in clean
        assert clean == "Hola mundo\n\nPruebade texto."
