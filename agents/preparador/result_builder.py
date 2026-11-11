"""
Construcción y Validación Estricta de Resultados para el Agente Preparador.

Responsabilidad delimitada:
- Evaluar los resultados acumulados en `PreparationSessionContext` tras la ejecución de las herramientas.
- Construir y validar formalmente `PreparationResult`, diferenciando:
  * Falta de ejecución de `tool_validar_entrada` (`fallo_herramienta` -> `error`).
  * Fallo técnico en validación (`VALIDATION_TOOL_ERROR` -> `error`).
  * Entrada inválida (`entrada_invalida` -> `error`).
  * Fallo técnico en OCR (`fallo_herramienta` -> `error`) o captura ilegible (`texto_no_extraible` -> `incompleto`).
  * Preparación exitosa con o sin enlaces (`con_enlaces` / `sin_enlaces` -> `correcto`).
"""

from __future__ import annotations

from typing import List, Optional

from agents.common.contracts import PreparationResult
from agents.tools.preparation_tools import PreparationSessionContext


def _build_incomplete_or_error_result(
    ctx: PreparationSessionContext,
    loaded_skills: List[str],
    estado: str,
    detalle_estado: str,
    mensaje_error: str,
    include_ocr_warnings: bool = False,
) -> PreparationResult:
    """Construye y valida un `PreparationResult` para casos no exitosos."""
    res = PreparationResult(
        estado=estado,  # type: ignore[arg-type]
        detalle_estado=detalle_estado,  # type: ignore[arg-type]
        texto_extraido_o_recibido="",
        enlaces_encontrados=[],
        advertencias=list(ctx.warnings),
        mensaje_error=mensaje_error,
        modalidad_entrada=ctx.input_mode,
        ocr_url_warnings=list(ctx.ocr_url_warnings) if include_ocr_warnings else [],
        skills_cargadas=list(loaded_skills),
        herramientas_invocadas=list(ctx.tools_called),
    )
    res.validate()
    return res


def build_validated_preparation_result(
    ctx: PreparationSessionContext,
    loaded_skills: List[str],
) -> PreparationResult:
    """
    Construye y valida el contrato `PreparationResult` a partir de los resultados
    reales de las herramientas invocadas por el Agente Preparador.
    """
    if not ctx.validation_done:
        return _build_incomplete_or_error_result(
            ctx,
            loaded_skills,
            estado="error",
            detalle_estado="fallo_herramienta",
            mensaje_error="El Agente Preparador no ejecutó la herramienta obligatoria 'tool_validar_entrada'.",
        )

    if ctx.validation_error_code == "VALIDATION_TOOL_ERROR":
        return _build_incomplete_or_error_result(
            ctx,
            loaded_skills,
            estado="error",
            detalle_estado="fallo_herramienta",
            mensaje_error=ctx.validation_error_message or "Fallo interno en la herramienta de validación.",
        )

    if not ctx.is_input_valid:
        return _build_incomplete_or_error_result(
            ctx,
            loaded_skills,
            estado="error",
            detalle_estado="entrada_invalida",
            mensaje_error=ctx.validation_error_message or "La entrada proporcionada no es válida.",
        )

    if ctx.input_mode == "ocr_screenshot":
        if not ctx.ocr_executed or ctx.ocr_status == "tool_error":
            return _build_incomplete_or_error_result(
                ctx,
                loaded_skills,
                estado="error",
                detalle_estado="fallo_herramienta",
                mensaje_error=ctx.ocr_error_message or "Falló la herramienta de extracción de texto OCR.",
            )

        if ctx.ocr_status == "empty_or_illegible" or not ctx.raw_active_text.strip():
            return _build_incomplete_or_error_result(
                ctx,
                loaded_skills,
                estado="incompleto",
                detalle_estado="texto_no_extraible",
                mensaje_error=ctx.ocr_error_message or "No se pudo extraer texto legible de la captura.",
                include_ocr_warnings=True,
            )

    detalle: str = "con_enlaces" if ctx.extracted_urls else "sin_enlaces"
    res = PreparationResult(
        estado="correcto",
        detalle_estado=detalle,  # type: ignore[arg-type]
        texto_extraido_o_recibido=ctx.raw_active_text,
        enlaces_encontrados=list(ctx.extracted_urls),
        advertencias=list(ctx.warnings),
        mensaje_error=None,
        modalidad_entrada=ctx.input_mode,
        url_details=list(ctx.url_details),
        ocr_url_warnings=list(ctx.ocr_url_warnings),
        skills_cargadas=list(loaded_skills),
        herramientas_invocadas=list(ctx.tools_called),
    )
    res.validate()
    return res

