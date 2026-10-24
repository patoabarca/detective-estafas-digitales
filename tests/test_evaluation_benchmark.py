"""
Pruebas Automatizadas de Regresión sobre el Banco de Evaluación.
Proyecto: Detective de Estafas Digitales

Valida que el detector mantenga un rendimiento estadístico riguroso
(F1-Score >= 95%, Precisión >= 95%, Recall >= 95%) tanto en el subconjunto
de desarrollo como en el subconjunto de evaluación reservada (Test Set).
"""

import pytest
from scripts.evaluate_dataset import evaluate_benchmark, DATASET
from scripts.worker import run_pipeline


def test_benchmark_dev_split_metrics():
    """Valida métricas formales en el subconjunto de desarrollo (Dev)."""
    metrics = evaluate_benchmark(split="dev")
    assert metrics["total_cases"] == 20
    assert metrics["precision"] >= 0.95
    assert metrics["recall"] >= 0.95
    assert metrics["f1_score"] >= 0.95
    assert metrics["fp"] == 0
    assert metrics["fn"] == 0


def test_benchmark_test_split_metrics():
    """Valida métricas formales en el subconjunto de evaluación reservada (Test)."""
    metrics = evaluate_benchmark(split="test")
    assert metrics["total_cases"] == 20
    assert metrics["precision"] >= 0.95
    assert metrics["recall"] >= 0.95
    assert metrics["f1_score"] >= 0.95
    assert metrics["fp"] == 0
    assert metrics["fn"] == 0


def test_case_1_correo_baja_jornada_phishing():
    """
    Caso 1 de la auditoría:
    Amenaza con dar de baja la cuenta al finalizar la jornada + verificación + URL .online.
    Debe clasificar en RIESGO ALTO.
    """
    msg = (
        "Aviso de soporte técnico: Procederemos a dar de baja su cuenta de correo "
        "al finalizar la jornada por falta de actualización. "
        "Por favor, complete una verificación en: "
        "https://correo-validacion.seguridad-cuentas.online"
    )
    report = run_pipeline(msg)
    assert report["status"] == "success"
    risk = report["risk_assessment"]
    assert risk["level"] == "ALTO"
    assert risk["score"] >= 75
    # Verificar activación de reglas esenciales
    rule_ids = [r.split()[0].strip() for r in risk["activated_rules"]]
    assert "REGLA-ING-01" in rule_ids  # Amenaza de baja
    assert "REGLA-ING-02" in rule_ids  # Urgencia temporal (al finalizar la jornada)
    assert "REGLA-FRA-01" in rule_ids  # Solicitud de verificación


def test_case_2_capacitacion_seguridad_no_false_positive():
    """
    Caso 2 de la auditoría:
    Invitación a capacitación que menciona contraseñas y bloqueos sin pedir credenciales.
    Debe clasificar en RIESGO BAJO.
    """
    msg = (
        "Invitación al Taller de Ciberseguridad Corporativa: Este jueves a las 15:00 hs "
        "conversaremos sobre buenas prácticas en contraseñas seguras, prevención de bloqueos de cuentas "
        "y detección de fraudes digitales. Los esperamos en el auditorio principal."
    )
    report = run_pipeline(msg)
    assert report["status"] == "success"
    risk = report["risk_assessment"]
    assert risk["level"] == "BAJO"
    assert risk["score"] == 0
    assert len(risk["activated_rules"]) == 0


def test_case_santander_educational_advisory_no_false_positive():
    """
    Aviso legítimo de seguridad bancaria ('el banco nunca te pedirá tu clave').
    No debe activar falsos positivos por la mención de claves o banco.
    """
    msg = (
        "Recordatorio de Seguridad de Banco Santander: Recordá que nuestro personal nunca te llamará "
        "ni te enviará mensajes para pedirte tu clave de cajero, token de seguridad ni datos confidenciales. "
        "Cuidá tu información bancaria."
    )
    report = run_pipeline(msg)
    assert report["status"] == "success"
    risk = report["risk_assessment"]
    assert risk["level"] == "BAJO"
    assert risk["score"] == 0
