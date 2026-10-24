"""
Módulo de Adaptador entre la Interfaz Web y el Motor Determinístico de Análisis.

Este adaptador permite que la interfaz Streamlit invoque directamente los módulos
de inspección estática (scripts/analyzer.py, scripts/url_analyzer.py, scripts/risk_classifier.py
y scripts/report_generator.py) SIN requerir llamadas a shell ni subprocesos,
garantizando aislamiento de memoria, mínimo privilegio y cero conexiones de red.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, Optional
import unicodedata

# Asegurar que el directorio scripts/ esté disponible en sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from worker import run_pipeline, load_policy
except ImportError:
    # Importación alternativa si sys.path difiere
    from scripts.worker import run_pipeline, load_policy

# Telemetría de diagnóstico desactivada por defecto (activable vía variable de entorno)
ENABLE_DIAGNOSTICS = os.environ.get("DETECTIVE_DIAGNOSTICS", "false").lower() in ("true", "1", "yes")


def normalize_text_content(text: str) -> str:
    """
    Normaliza el texto de forma segura y consistente entre modalidades (OCR y texto directo):
    - Normalización canónica Unicode NFKC.
    - Conversión de espacios no separables (\\u00a0, \\u202f) a espacios estándar (\\x20).
    - Eliminación de caracteres invisibles o de control (\\u200b, \\ufeff).
    - Normalización de saltos de línea (CRLF -> LF).
    - Eliminación de espacios superfluos iniciales y finales.
    """
    if not text:
        return ""

    # 1. Normalización Unicode estándar (NFKC)
    norm = unicodedata.normalize("NFKC", text)

    # 2. Reemplazo de espacios no separables por espacios estándar
    norm = norm.replace("\u00a0", " ").replace("\u202f", " ")

    # 3. Eliminación de caracteres invisibles / de control no imprimibles
    norm = re.sub(r"[\u200b\u200c\u200d\ufeff\x00-\x08\x0b\x0c\x0e-\x1f]", "", norm)

    # 4. Normalización de saltos de línea
    norm = norm.replace("\r\n", "\n").replace("\r", "\n")

    return norm.strip()


def create_diagnostic_entry(
    input_mode: str,
    text: str,
    report: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Registra metadatos de auditoría comparativa sin exponer PII ni contenido sensible.
    Conforme a la Sección 5 de la auditoría.
    """
    risk_info = report.get("risk_assessment", {})
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    rule_ids = [
        rule.split(":")[0].strip()
        for rule in risk_info.get("activated_rules", [])
    ]
    return {
        "flow_name": input_mode,
        "char_count": len(text),
        "sha256_hash": text_hash,
        "indicators_count": len(report.get("indicators_detected", [])),
        "risk_level": risk_info.get("level", "INDETERMINADO"),
        "score": risk_info.get("score", 0),
        "activated_rules": rule_ids,
    }


def analyze_text(
    text: str,
    input_mode: str = "text",
    custom_policy: Optional[Dict[str, Any]] = None,
    enable_diagnostics: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Ejecuta el análisis de riesgo determinístico sobre el texto provisto.

    Parámetros:
        text (str): Contenido textual del mensaje (provisto directamente o extraído por OCR).
        input_mode (str): Modalidad de entrada ('text' o 'ocr_screenshot').
        custom_policy (dict, opcional): Política personalizada de ponderaciones.
        enable_diagnostics (bool, opcional): Forzar inclusión de telemetría de diagnóstico.

    Retorna:
        Dict[str, Any]: Reporte estructurado con nivel de riesgo, indicadores,
                        auditoría de URLs y recomendaciones.
    """
    if text is None:
        text = ""

    # Normalizar espacios, Unicode y saltos de línea de forma robusta
    cleaned_text = normalize_text_content(text)

    policy = custom_policy or load_policy()
    max_chars = policy.get("runtime_constraints", {}).get("max_input_chars", 15000)

    # Validación de longitud máxima defensiva
    if len(cleaned_text) > max_chars:
        return {
            "status": "error",
            "error_type": "LengthExceededError",
            "message": (
                f"El texto analizado ({len(cleaned_text)} caracteres) excede el límite máximo "
                f"de seguridad de {max_chars} caracteres."
            ),
            "input_mode": input_mode,
        }

    try:
        report = run_pipeline(cleaned_text, policy)
        # Añadir metadatos de la modalidad de entrada
        report["input_mode"] = input_mode
        report["input_char_count"] = len(cleaned_text)

        # Telemetría segura de diagnóstico (opcional)
        should_diag = enable_diagnostics if enable_diagnostics is not None else ENABLE_DIAGNOSTICS
        if should_diag:
            report["diagnostic_telemetry"] = create_diagnostic_entry(
                input_mode, cleaned_text, report
            )

        return report

    except Exception as exc:
        return {
            "status": "error",
            "error_type": exc.__class__.__name__,
            "message": f"Ocurrió un error inesperado durante el análisis: {str(exc)}",
            "input_mode": input_mode,
        }

