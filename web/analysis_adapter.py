"""
Módulo de Adaptador entre la Interfaz Web y el Motor Determinístico de Análisis.

Este adaptador permite que la interfaz Streamlit invoque directamente los módulos
de inspección estática (scripts/analyzer.py, scripts/url_analyzer.py, scripts/risk_classifier.py
y scripts/report_generator.py) SIN requerir llamadas a shell ni subprocesos,
garantizando aislamiento de memoria, mínimo privilegio y cero conexiones de red.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional

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


def analyze_text(
    text: str,
    input_mode: str = "text",
    custom_policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Ejecuta el análisis de riesgo determinístico sobre el texto provisto.

    Parámetros:
        text (str): Contenido textual del mensaje (provisto directamente o extraído por OCR).
        input_mode (str): Modalidad de entrada ('text' o 'ocr_screenshot').
        custom_policy (dict, opcional): Política personalizada de ponderaciones.

    Retorna:
        Dict[str, Any]: Reporte estructurado con nivel de riesgo, indicadores,
                        auditoría de URLs y recomendaciones.
    """
    if text is None:
        text = ""

    # Normalizar espacios y saltos de línea de forma segura
    cleaned_text = text.strip()

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
        return report

    except Exception as exc:
        return {
            "status": "error",
            "error_type": exc.__class__.__name__,
            "message": f"Ocurrió un error inesperado durante el análisis: {str(exc)}",
            "input_mode": input_mode,
        }
