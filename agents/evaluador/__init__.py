"""
Módulo del Agente Evaluador (Etapa 4).

Consolida los hallazgos validados de los agentes especialistas, calcula el puntaje
heurístico mediante reglas Python documentadas, asigna el nivel de riesgo, genera
la explicación no técnica, selecciona recomendaciones preventivas del sistema y
genera el informe PDF descargable.
"""

from __future__ import annotations

from agents.evaluador.agent import (
    EVALUADOR_ALLOWED_SKILLS,
    EVALUADOR_TOOL_DECLARATIONS,
    EvaluadorAgent,
)

__all__ = [
    "EVALUADOR_ALLOWED_SKILLS",
    "EVALUADOR_TOOL_DECLARATIONS",
    "EvaluadorAgent",
]

