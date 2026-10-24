"""
Pruebas del Módulo de Exportación de Informes PDF (web/pdf_exporter.py).
"""

import pytest
from web.analysis_adapter import analyze_text
from web.pdf_exporter import generate_pdf_report


class TestPDFExport:
    """Pruebas de generación y consistencia de informes en formato PDF."""

    def test_generate_pdf_from_phishing_report(self):
        msg = (
            "Estimado cliente, su cuenta bancaria será bloqueada hoy. "
            "Ingrese a https://galicia-validacion.seguridad-bancaria.online y confirme su token de seguridad."
        )
        report = analyze_text(msg, input_mode="ocr_screenshot")
        pdf_bytes = generate_pdf_report(report)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 2000
        # Cabecera estándar de formato PDF
        assert pdf_bytes.startswith(b"%PDF-")

    def test_generate_pdf_from_legitimate_report(self):
        msg = "Hola Juan, tu pedido ha sido despachado. Gracias por tu compra."
        report = analyze_text(msg, input_mode="text")
        pdf_bytes = generate_pdf_report(report)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b"%PDF-")

    def test_generate_pdf_from_indeterminate_report(self):
        report = analyze_text("", input_mode="text")
        pdf_bytes = generate_pdf_report(report)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b"%PDF-")

    def test_pdf_handles_spanish_accents_and_special_chars(self):
        special_report = {
            "status": "success",
            "timestamp": "2026-10-23T20:00:00Z",
            "input_mode": "text",
            "risk_assessment": {
                "level": "ALTO",
                "score": 90,
                "summary": "¡Atención! ¿Confirmó su contraseña? Señales de estafa con cañón, ñandú y verificación rápida.",
                "activated_rules": ["REGLA-PRUEBA (+50 pts): Caracteres acentuados áéíóú ÁÉÍÓÚ ñÑ ¿?"],
            },
            "indicators_detected": [
                {
                    "id": "IND-ESPECIAL",
                    "category": "prueba_lingüística",
                    "severity": "ALTA",
                    "description": "Texto con tildes (canción, crédito) y signos de apertura (¿ ¡).",
                    "evidence_snippets": ["confirmación bancaria", "año"],
                }
            ],
            "url_analysis": [
                {
                    "raw_url": "https://sitio-engañoso.online/login",
                    "domain": "sitio-engañoso.online",
                    "findings": ["Uso de caracteres latinos."],
                }
            ],
            "recommendations": ["No introduzcas contraseñas.", "Verificá en la sucursal."],
            "limitations": ["Evaluación local estática."],
            "non_technical_explanation": "Explicación en español neutro con acentuación correcta.",
        }

        pdf_bytes = generate_pdf_report(special_report)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF-")
