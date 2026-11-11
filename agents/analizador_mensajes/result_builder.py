"""
Construcción y Validación Estricta de Resultados para el Agente Analizador de Mensajes.

Responsabilidad delimitada:
- Evaluar los hallazgos y categorías revisadas acumulados en `MessageAnalysisSessionState`.
- Diferenciar los 3 estados contractuales:
  1. Fallo técnico en alguna herramienta (`estado="error"`).
  2. Categorías obligatorias omitidas (`estado="incompleto"`, nunca `"correcto"`).
  3. Las 5 categorías revisadas (`estado="correcto"`).
- Validar formalmente la evidencia literal mediante `MessageAnalysisResult.validate()`.
"""

from __future__ import annotations

from typing import List

from agents.common.contracts import (
    MessageAnalysisResult,
    REQUIRED_MESSAGE_ANALYSIS_CATEGORIES,
)
from agents.tools.message_analysis_tools import MessageAnalysisSessionState
from agents.tools.preparation_tools import PreparationSessionContext


def build_validated_message_analysis_result(
    prep_ctx: PreparationSessionContext,
    msg_state: MessageAnalysisSessionState,
    loaded_skills: List[str],
) -> MessageAnalysisResult:
    """
    Construye y valida exhaustivamente el contrato `MessageAnalysisResult` a partir
    del estado acumulado en `msg_state` y del texto original en `prep_ctx`.
    """
    loaded_skill_names = list(loaded_skills)
    tools_called = list(msg_state.tools_called)
    analyzed_text = prep_ctx.raw_active_text

    categorias_revisadas = [
        c for c in REQUIRED_MESSAGE_ANALYSIS_CATEGORIES if c in msg_state.categories_reviewed
    ]
    categorias_sin_hallazgos = [
        c
        for c in REQUIRED_MESSAGE_ANALYSIS_CATEGORIES
        if msg_state.category_status.get(c) == "revisada_sin_hallazgos"
    ]
    categorias_no_revisadas = [
        c
        for c in REQUIRED_MESSAGE_ANALYSIS_CATEGORIES
        if msg_state.category_status.get(c) == "no_revisada"
    ]
    findings_list = list(msg_state.findings_by_id.values())

    if msg_state.tool_errors:
        res = MessageAnalysisResult(
            estado="error",
            categorias_revisadas=categorias_revisadas,
            categorias_sin_hallazgos=categorias_sin_hallazgos,
            categorias_no_revisadas=categorias_no_revisadas,
            estado_categorias=dict(msg_state.category_status),
            senales_encontradas=findings_list,
            advertencias=list(msg_state.warnings),
            mensaje_error="; ".join(msg_state.tool_errors),
            skills_cargadas=loaded_skill_names,
            herramientas_invocadas=tools_called,
        )
        res.validate(analyzed_text=analyzed_text)
        return res

    if categorias_no_revisadas:
        warn_missing = (
            f"Análisis incompleto: no se revisaron las categorías obligatorias: "
            f"{', '.join(categorias_no_revisadas)}."
        )
        warnings = list(msg_state.warnings)
        if warn_missing not in warnings:
            warnings.append(warn_missing)
        res = MessageAnalysisResult(
            estado="incompleto",
            categorias_revisadas=categorias_revisadas,
            categorias_sin_hallazgos=categorias_sin_hallazgos,
            categorias_no_revisadas=categorias_no_revisadas,
            estado_categorias=dict(msg_state.category_status),
            senales_encontradas=findings_list,
            advertencias=warnings,
            mensaje_error=warn_missing,
            skills_cargadas=loaded_skill_names,
            herramientas_invocadas=tools_called,
        )
        res.validate(analyzed_text=analyzed_text)
        return res

    res = MessageAnalysisResult(
        estado="correcto",
        categorias_revisadas=categorias_revisadas,
        categorias_sin_hallazgos=categorias_sin_hallazgos,
        categorias_no_revisadas=[],
        estado_categorias=dict(msg_state.category_status),
        senales_encontradas=findings_list,
        advertencias=list(msg_state.warnings),
        mensaje_error=None,
        skills_cargadas=loaded_skill_names,
        herramientas_invocadas=tools_called,
    )
    res.validate(analyzed_text=analyzed_text)
    return res
