"""
Construcción y Validación Estricta de Resultados para el Agente Analizador de Enlaces.

Responsabilidad delimitada:
- Evaluar los resultados reunidos en `UrlAnalysisSessionState` tras la ejecución de las herramientas.
- Manejar los 5 casos de estado:
  1. Error técnico en la herramienta (`fallo_herramienta` -> estado='error').
  2. Sesión sin enlaces (`sin_enlaces` -> estado='correcto', no es error).
  3. Enlaces omitidos por el agente (`enlaces_omitidos` -> estado='incompleto').
  4. Dirección malformada / host no parseable (`direccion_no_analizable` -> estado='incompleto').
  5. Análisis completo de todos los enlaces (`analizados_con_senales` o `analizados_sin_senales` con advertencia de no garantía).
- Ordenar canónicamente los enlaces según el mapa de preparación.
- Validar formalmente el contrato resultante `UrlAnalysisResult`.
"""

from __future__ import annotations

from typing import List

from agents.common.contracts import UrlAnalysisResult, UrlItemAnalysisResult
from agents.tools.preparation_tools import PreparationSessionContext
from agents.tools.url_analysis_tools import NON_GUARANTEE_WARNING, UrlAnalysisSessionState


def build_validated_url_analysis_result(
    prep_ctx: PreparationSessionContext,
    url_state: UrlAnalysisSessionState,
    loaded_skills: List[str],
) -> UrlAnalysisResult:
    """
    Construye y valida exhaustivamente el contrato `UrlAnalysisResult` a partir del
    estado acumulado por `tool_analizar_url`.
    """
    tools_called = list(url_state.tools_called)
    expected_urls = list(prep_ctx.extracted_urls)
    total_extracted = len(prep_ctx.url_id_map)

    # Ordenar los ítems analizados según el orden canónico de prep_ctx.url_id_map
    ordered_items: List[UrlItemAnalysisResult] = []
    omitted_ids: List[str] = []
    for uid in prep_ctx.url_id_map.keys():
        if uid in url_state.analyzed_items_by_id:
            ordered_items.append(url_state.analyzed_items_by_id[uid])
        else:
            omitted_ids.append(uid)

    processed_count = len(ordered_items)
    warnings = list(url_state.warnings)

    # Caso 1: Error técnico en la herramienta
    if url_state.tool_errors:
        res = UrlAnalysisResult(
            estado="error",
            detalle_estado="fallo_herramienta",
            intervino_agente=True,
            motivo_omision=None,
            cantidad_enlaces_extraidos=total_extracted,
            cantidad_enlaces_procesados=processed_count,
            enlaces_analizados=ordered_items,
            enlaces_omitidos=omitted_ids,
            advertencias=warnings,
            mensaje_error="; ".join(url_state.tool_errors),
            skills_cargadas=loaded_skills,
            herramientas_invocadas=tools_called,
        )
        res.validate(expected_urls=expected_urls)
        return res

    # Caso 2: No había enlaces en la sesión
    if total_extracted == 0:
        res = UrlAnalysisResult(
            estado="correcto",
            detalle_estado="sin_enlaces",
            intervino_agente=True,
            motivo_omision="No había enlaces en el mensaje preparado.",
            cantidad_enlaces_extraidos=0,
            cantidad_enlaces_procesados=0,
            enlaces_analizados=[],
            enlaces_omitidos=[],
            advertencias=warnings,
            mensaje_error=None,
            skills_cargadas=loaded_skills,
            herramientas_invocadas=tools_called,
        )
        res.validate(expected_urls=expected_urls)
        return res

    # Caso 3: El agente omitió analizar uno o más enlaces extraídos -> NUNCA marcar como "correcto"
    if omitted_ids or processed_count < total_extracted:
        warn_omitted = (
            f"Análisis de enlaces incompleto: se omitieron los enlaces {omitted_ids} "
            f"(procesados {processed_count} de {total_extracted})."
        )
        if warn_omitted not in warnings:
            warnings.append(warn_omitted)
        res = UrlAnalysisResult(
            estado="incompleto",
            detalle_estado="enlaces_omitidos",
            intervino_agente=True,
            motivo_omision=None,
            cantidad_enlaces_extraidos=total_extracted,
            cantidad_enlaces_procesados=processed_count,
            enlaces_analizados=ordered_items,
            enlaces_omitidos=omitted_ids,
            advertencias=warnings,
            mensaje_error=warn_omitted,
            skills_cargadas=loaded_skills,
            herramientas_invocadas=tools_called,
        )
        res.validate(expected_urls=expected_urls)
        return res

    # Caso 4: Algún enlace tenía una dirección malformada o no pudo analizarse -> estado "incompleto"
    unparseable_items = [
        it for it in ordered_items if it.estado_enlace == "direccion_no_analizable"
    ]
    if unparseable_items:
        unparseable_ids = [it.url_id for it in unparseable_items]
        warn_unp = (
            f"Una o más direcciones no pudieron analizarse por formato inválido o host no identificable: "
            f"{unparseable_ids}."
        )
        if warn_unp not in warnings:
            warnings.append(warn_unp)
        res = UrlAnalysisResult(
            estado="incompleto",
            detalle_estado="direccion_no_analizable",
            intervino_agente=True,
            motivo_omision=None,
            cantidad_enlaces_extraidos=total_extracted,
            cantidad_enlaces_procesados=processed_count,
            enlaces_analizados=ordered_items,
            enlaces_omitidos=[],
            advertencias=warnings,
            mensaje_error=warn_unp,
            skills_cargadas=loaded_skills,
            herramientas_invocadas=tools_called,
        )
        res.validate(expected_urls=expected_urls)
        return res

    # Caso 5: Todos los enlaces fueron analizados correctamente
    any_with_signals = any(
        it.estado_enlace == "analizado_con_senales" for it in ordered_items
    )
    detalle = (
        "analizados_con_senales" if any_with_signals else "analizados_sin_senales"
    )
    if not any_with_signals and NON_GUARANTEE_WARNING not in warnings:
        warnings.append(NON_GUARANTEE_WARNING)

    res = UrlAnalysisResult(
        estado="correcto",
        detalle_estado=detalle,  # type: ignore[arg-type]
        intervino_agente=True,
        motivo_omision=None,
        cantidad_enlaces_extraidos=total_extracted,
        cantidad_enlaces_procesados=processed_count,
        enlaces_analizados=ordered_items,
        enlaces_omitidos=[],
        advertencias=warnings,
        mensaje_error=None,
        skills_cargadas=loaded_skills,
        herramientas_invocadas=tools_called,
    )
    res.validate(expected_urls=expected_urls)
    return res
