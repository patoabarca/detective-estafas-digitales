"""
Construcción y Validación Estricta de Resultados para el Agente Evaluador.

Responsabilidad delimitada:
- Garantizar la salvaguarda de que una preparación o análisis incompleto o con error
  siempre produzca nivel `INDETERMINADO` y puntaje `0` (nunca `BAJO`).
- Ensamblar y validar el contrato `EvaluationResult` a partir de `EvaluationSessionState`,
  completando la explicación y recomendaciones determinísticas desde `ReportGenerator` si
  corresponde.
"""

from __future__ import annotations

from typing import List, Optional

from agents.common.contracts import (
    EvaluationResult,
    MessageAnalysisResult,
    PreparationResult,
    UrlAnalysisResult,
)
from agents.tools.evaluation_tools import EvaluationSessionState
from scripts.report_generator import ReportGenerator


def _build_incomplete_evaluation_result(
    state: EvaluationSessionState,
    loaded_skills: List[str],
    prior_estado: str,
    detalle_estado: str,
    resumen: str,
    explicacion: str,
    recomendaciones: List[str],
    mensaje_error: Optional[str],
) -> EvaluationResult:
    """Construye y valida un `EvaluationResult` seguro (`INDETERMINADO`) ante etapas previas fallidas."""
    res = EvaluationResult(
        estado="incompleto" if prior_estado == "incompleto" else "error",
        detalle_estado=detalle_estado,
        nivel_riesgo="INDETERMINADO",
        puntaje=0,
        resumen=resumen,
        explicacion_no_tecnica=explicacion,
        recomendaciones=recomendaciones,
        limitaciones=list(ReportGenerator.LIMITATIONS),
        hallazgos_unificados=list(state.unified_indicators),
        analisis_urls=list(state.unified_url_analyses),
        reglas_activadas=[],
        skills_cargadas=list(loaded_skills),
        herramientas_invocadas=list(state.tools_called),
        pdf_generado=False,
        pdf_filename=None,
        advertencias=list(state.warnings),
        mensaje_error=mensaje_error,
    )
    res.validate()
    return res


def build_validated_evaluation_result(
    state: EvaluationSessionState,
    prep_res: PreparationResult,
    msg_res: MessageAnalysisResult,
    url_res: Optional[UrlAnalysisResult],
    loaded_skills: List[str],
) -> EvaluationResult:
    """
    Construye y valida el contrato `EvaluationResult` aplicando salvaguardas ante
    análisis previos incompletos o fallidos.
    """
    if prep_res.estado != "correcto":
        return _build_incomplete_evaluation_result(
            state=state,
            loaded_skills=loaded_skills,
            prior_estado=prep_res.estado,
            detalle_estado=f"preparacion_{prep_res.detalle_estado}",
            resumen=f"Evaluación incompleta debido al estado de la preparación ({prep_res.detalle_estado}).",
            explicacion=(
                "No fue posible completar la evaluación de seguridad debido a que la preparación "
                "de la entrada no fue exitosa."
            ),
            recomendaciones=["Revisar el mensaje manualmente.", "No hacer clic en enlaces sospechosos."],
            mensaje_error=prep_res.mensaje_error,
        )

    if msg_res.estado != "correcto":
        return _build_incomplete_evaluation_result(
            state=state,
            loaded_skills=loaded_skills,
            prior_estado=msg_res.estado,
            detalle_estado=f"mensaje_{msg_res.estado}",
            resumen=f"Evaluación incompleta debido a categorías omitidas en el análisis del mensaje ({msg_res.estado}).",
            explicacion=(
                "No se pudo determinar el nivel de riesgo con certeza porque el análisis de señales "
                "del mensaje quedó incompleto."
            ),
            recomendaciones=[
                "Desconfiar de mensajes con remitente desconocido.",
                "Verificar por canales oficiales independientes.",
            ],
            mensaje_error=msg_res.mensaje_error,
        )

    if url_res is not None and url_res.intervino_agente and url_res.estado != "correcto":
        return _build_incomplete_evaluation_result(
            state=state,
            loaded_skills=loaded_skills,
            prior_estado=url_res.estado,
            detalle_estado=f"enlaces_{url_res.detalle_estado}",
            resumen=f"Evaluación incompleta debido a direcciones no analizables en los enlaces ({url_res.detalle_estado}).",
            explicacion=(
                "Se detectaron enlaces en el mensaje que no pudieron ser auditados completamente. "
                "Por precaución, no ingrese a los mismos."
            ),
            recomendaciones=[
                "No abrir ningún enlace recibido.",
                "Consultar directamente el sitio oficial escribiendo la dirección en el navegador.",
            ],
            mensaje_error=url_res.mensaje_error,
        )

    explanation = state.explanation
    if not explanation:
        report_gen = ReportGenerator()
        has_inj = any(ind.get("id") == "SEC-PROMPT-INJECTION" for ind in state.unified_indicators)
        explanation = report_gen.build_non_technical_explanation(
            risk_level=state.level,
            indicators=state.unified_indicators,
            url_analyses=state.unified_url_analyses,
            prompt_injection=has_inj,
        )

    recs = state.recommendations
    if not recs:
        has_urls = len(state.unified_url_analyses) > 0
        has_creds = any(ind.get("id") == "FRA-CAPTURA-CREDENCIALES" for ind in state.unified_indicators)
        recs = list(
            ReportGenerator.get_recommendations(
                risk_level=state.level,
                has_urls=has_urls,
                has_creds=has_creds,
            )
        )

    res = EvaluationResult(
        estado="correcto",
        detalle_estado="evaluacion_completa",
        nivel_riesgo=state.level,
        puntaje=state.score,
        resumen=state.summary,
        explicacion_no_tecnica=explanation,
        recomendaciones=recs,
        limitaciones=list(ReportGenerator.LIMITATIONS),
        hallazgos_unificados=list(state.unified_indicators),
        analisis_urls=list(state.unified_url_analyses),
        reglas_activadas=state.activated_rules,
        skills_cargadas=list(loaded_skills),
        herramientas_invocadas=list(state.tools_called),
        pdf_generado=state.pdf_generated,
        pdf_filename=state.pdf_filename,
        advertencias=list(state.warnings),
    )
    res.validate()
    return res
