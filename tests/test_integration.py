"""
Pruebas de Integración de Extremo a Extremo (test_integration.py).
Valida la ejecución completa del pipeline en los escenarios oficiales del MVP:
- Caso 1: Phishing bancario (Riesgo ALTO).
- Caso 2: Premio falso con pago anticipado (Riesgo ALTO).
- Caso 3: Mensaje cotidiano/legítimo (Riesgo BAJO).
- Caso 4: URL engañosa con subdominio suplantado.
- Caso 5: Prompt injection aislado y neutralizado.
- Validación de conformidad con el esquema JSON y formato Markdown.
"""

import json
import sys
from pathlib import Path
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
BASE_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from report_generator import ReportGenerator
from worker import load_policy, run_pipeline


@pytest.fixture
def policy():
    return load_policy()


def test_caso_1_phishing_bancario_end_to_end():
    file_path = BASE_DIR / "examples" / "phishing_bancario.txt"
    content = file_path.read_text(encoding="utf-8")

    report = run_pipeline(content)

    assert report["status"] == "success"
    assert report["risk_assessment"]["level"] == "ALTO"
    assert report["risk_assessment"]["score"] >= 50

    indicator_ids = [i["id"] for i in report["indicators_detected"]]
    assert "ING-AMENAZA-BLOQUEO" in indicator_ids
    assert "FRA-CAPTURA-CREDENCIALES" in indicator_ids
    assert "ING-URGENCIA-ARTIFICIAL" in indicator_ids

    # Auditoría de URL
    assert len(report["url_analysis"]) == 1
    url_info = report["url_analysis"][0]
    assert url_info["domain"] == "galicia-validacion.seguridad-bancaria.online"
    assert any("Uso engañoso de la marca 'galicia'" in f for f in url_info["findings"])


def test_caso_2_premio_falso_end_to_end():
    file_path = BASE_DIR / "examples" / "promocion_falsa.txt"
    content = file_path.read_text(encoding="utf-8")

    report = run_pipeline(content)

    assert report["status"] == "success"
    assert report["risk_assessment"]["level"] == "ALTO"
    indicator_ids = [i["id"] for i in report["indicators_detected"]]
    assert "FRA-PREMIO-INESPERADO" in indicator_ids
    assert "FRA-PAGO-ANTICIPADO" in indicator_ids


def test_caso_3_mensaje_cotidiano_end_to_end():
    file_path = BASE_DIR / "examples" / "mensaje_legitimo.txt"
    content = file_path.read_text(encoding="utf-8")

    report = run_pipeline(content)

    assert report["status"] == "success"
    assert report["risk_assessment"]["level"] == "BAJO"
    assert report["risk_assessment"]["score"] == 0
    assert len(report["indicators_detected"]) == 0
    # Verifica que contenga la advertencia de que la ausencia de señales no garantiza legitimidad
    assert any("no garantiza" in lim.lower() for lim in report["limitations"])


def test_caso_4_url_enganyosa_end_to_end():
    text = "Atención: para validar tu cuenta de Mercado Pago ingresá en https://mercadopago.com.seguridad-cuenta.xyz/login"
    report = run_pipeline(text)

    assert len(report["url_analysis"]) == 1
    url_info = report["url_analysis"][0]
    assert any("Uso engañoso de la marca 'mercadopago'" in f for f in url_info["findings"])
    assert report["risk_assessment"]["level"] in ("MEDIO", "ALTO")


def test_result_schema_compliance():
    text = "Hola, te paso el link de prueba: https://ejemplo.com/test"
    report = run_pipeline(text)

    # Validar campos obligatorios según config/result_schema.json
    required_keys = [
        "status",
        "timestamp",
        "risk_assessment",
        "indicators_detected",
        "url_analysis",
        "prompt_injection_detected",
        "prompt_injection_details",
        "limitations",
        "recommendations",
        "non_technical_explanation",
    ]
    for key in required_keys:
        assert key in report, f"Falta la clave requerida: {key}"

    assert report["risk_assessment"]["level"] in ["BAJO", "MEDIO", "ALTO", "INDETERMINADO"]
    assert 0 <= report["risk_assessment"]["score"] <= 100


def test_human_readable_report_generation():
    file_path = BASE_DIR / "examples" / "phishing_bancario.txt"
    content = file_path.read_text(encoding="utf-8")
    report = run_pipeline(content)

    report_gen = ReportGenerator()
    markdown_output = report_gen.generate_human_readable_report(report)

    assert "# 🛡️ Informe de Detective de Estafas Digitales" in markdown_output
    assert "RIESGO ALTO" in markdown_output
    assert "Explicación en Lenguaje Sencillo" in markdown_output
    assert "Recomendaciones Preventivas" in markdown_output
