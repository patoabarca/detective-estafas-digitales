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


def test_benchmark_manual8_split_metrics():
    """Valida los 8 casos de la auditoría manual."""
    metrics = evaluate_benchmark(split="manual8")
    assert metrics["total_cases"] == 8
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1_score"] == 1.0
    assert metrics["fp"] == 0
    assert metrics["fn"] == 0


def test_benchmark_heldout20_split_metrics():
    """Valida los 20 casos de evaluación independiente reservada (Held-out)."""
    metrics = evaluate_benchmark(split="heldout20")
    assert metrics["total_cases"] == 20
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1_score"] == 1.0
    assert metrics["fp"] == 0
    assert metrics["fn"] == 0


def test_manual_cases_individual_assertions():
    """Valida individualmente los casos 1, 3 y 4 de la evaluación manual."""
    # Caso 1: Paquete pendiente con pago
    case_1 = (
        "Hola, no pudimos entregar tu paquete porque falta validar el domicilio. "
        "El envío será devuelto al depósito al finalizar el día. Para reprogramar la entrega, "
        "confirmá tus datos y aboná el costo de gestión en https://entregas-confirmacion.paquetes-gestion.top"
    )
    rep1 = run_pipeline(case_1)
    assert rep1["risk_assessment"]["level"] == "ALTO"
    assert rep1["risk_assessment"]["score"] >= 80

    # Caso 3: Inhabilitación condicionada
    case_3 = (
        "Estimado usuario: detectamos actividad irregular en su cuenta. "
        "Por seguridad, el servicio permanecerá inhabilitado si no confirma su identidad antes del cierre de la jornada. "
        "Ingrese al centro de verificación y complete el procedimiento solicitado para continuar utilizando la plataforma."
    )
    rep3 = run_pipeline(case_3)
    assert rep3["risk_assessment"]["level"] == "ALTO"
    assert rep3["risk_assessment"]["score"] >= 75

    # Caso 4: Falso soporte SMS OTP
    case_4 = (
        "Buenas tardes, soy del soporte técnico. Detectamos un problema de sincronización con tu cuenta. "
        "Para resolverlo necesito que me compartas el código de seis dígitos que te acaba de llegar por SMS. "
        "No se lo pases a nadie más porque el código vence en cinco minutos."
    )
    rep4 = run_pipeline(case_4)
    assert rep4["risk_assessment"]["level"] == "ALTO"
    assert rep4["risk_assessment"]["score"] >= 65


def test_ambiguous_and_insufficient_text_yields_indeterminado():
    """
    Verifica que mensajes truncados, breves o ambiguos sin entidad ni enlace
    produzcan INDETERMINADO en lugar de BAJO.
    """
    short_ambiguous = "Hacé clic acá para validar"
    rep = run_pipeline(short_ambiguous)
    assert rep["risk_assessment"]["level"] == "INDETERMINADO"
    assert rep["risk_assessment"]["score"] == 0
    assert "REGLA-INDET" in rep["risk_assessment"]["activated_rules"][0]
