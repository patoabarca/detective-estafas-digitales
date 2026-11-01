"""
Herramientas Python Reutilizables y Acotadas para Preparación y Motor Determinístico.

Principios de Seguridad Aplicados en Código:
- Las herramientas NO aceptan rutas de archivos arbitrarias ni comandos shell.
- Operan sobre un contexto de sesión aislado en memoria (`PreparationSessionContext`),
  de modo que el LLM solo envía parámetros de control validados por lista blanca.
- El OCR se ejecuta 100% localmente sobre el objeto `PIL.Image` validado en memoria.
- La extracción de enlaces usa `scripts/url_analyzer.py` (Zero Network: nunca visita URLs).
- Antes de devolver cualquier texto extraído al LLM, se aplica `sanitize_text_for_external_llm`
  mientras se conserva `raw_active_text` en memoria local para el motor determinístico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from PIL import Image

from agents.common.contracts import ContractValidationError, validate_tool_arguments
from agents.common.privacy import SanitizationReport, sanitize_text_for_external_llm
from scripts.url_analyzer import analyze_urls_in_text, extract_urls
from scripts.worker import load_policy
from web.analysis_adapter import analyze_text, normalize_text_content
from web.image_processor import (
    ImageValidationError,
    preprocess_image_for_ocr,
    validate_and_load_image,
)
from web.ocr_service import get_ocr_service


@dataclass
class PreparationSessionContext:
    """
    Estado aislado en memoria para una solicitud individual de preparación/análisis.
    Evita que el LLM tenga que transportar bytes de imagen o textos sin enmascarar.
    """
    input_mode: str  # "text" | "ocr_screenshot"
    raw_input_text: str = ""
    image_bytes: Optional[bytes] = None
    image_filename: str = ""
    ocr_service_override: Optional[Any] = None

    # Estado interno poblado por las herramientas
    validation_done: bool = False
    is_input_valid: bool = False
    validation_error_code: Optional[str] = None
    validation_error_message: Optional[str] = None
    validated_image: Optional[Image.Image] = None
    image_metadata: Dict[str, Any] = field(default_factory=dict)

    # Texto original local (para el motor determinístico) y versión enmascarada (para el LLM)
    raw_active_text: str = ""
    masked_active_text: str = ""
    sanitization_report: Optional[SanitizationReport] = None

    ocr_executed: bool = False
    ocr_status: Optional[str] = None  # "ok" | "empty_or_illegible" | "tool_error"
    ocr_error_message: Optional[str] = None
    ocr_url_warnings: List[Dict[str, str]] = field(default_factory=list)

    links_extracted: bool = False
    extracted_urls: List[str] = field(default_factory=list)
    url_details: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    tools_called: List[str] = field(default_factory=list)


def execute_tool_validar_entrada(
    ctx: PreparationSessionContext,
    raw_args: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Herramienta Python de la skill `validar-entrada`.
    Valida tipo, longitud, tamaño en bytes, cabecera binaria y dimensiones.
    """
    validated_args = validate_tool_arguments(
        tool_name="tool_validar_entrada",
        args=raw_args,
        allowed_params={"input_mode": str},
        required_params=[],
    )
    requested_mode = validated_args.get("input_mode", ctx.input_mode)
    if requested_mode != ctx.input_mode:
        # Asegurar que siempre se valide la modalidad real de la sesión
        requested_mode = ctx.input_mode

    ctx.validation_done = True
    ctx.tools_called.append("tool_validar_entrada")

    policy = load_policy()
    max_chars = policy.get("runtime_constraints", {}).get("max_input_chars", 15000)

    if requested_mode == "text":
        normalized = normalize_text_content(ctx.raw_input_text)
        if not normalized:
            ctx.is_input_valid = False
            ctx.validation_error_code = "EMPTY_TEXT"
            ctx.validation_error_message = (
                "El texto ingresado está vacío o solo contiene espacios en blanco."
            )
            return {
                "status": "invalid",
                "is_valid": False,
                "input_mode": "text",
                "normalized_char_count": 0,
                "warnings": [],
                "error_code": ctx.validation_error_code,
                "error_message": ctx.validation_error_message,
            }

        if len(normalized) > max_chars:
            ctx.is_input_valid = False
            ctx.validation_error_code = "MAX_LENGTH_EXCEEDED"
            ctx.validation_error_message = (
                f"El texto ingresado ({len(normalized)} caracteres) supera el límite máximo "
                f"de seguridad de {max_chars} caracteres."
            )
            return {
                "status": "invalid",
                "is_valid": False,
                "input_mode": "text",
                "normalized_char_count": len(normalized),
                "warnings": [],
                "error_code": ctx.validation_error_code,
                "error_message": ctx.validation_error_message,
            }

        # Texto válido: guardar original localmente y versión enmascarada para el modelo
        ctx.is_input_valid = True
        ctx.raw_active_text = normalized
        san_report = sanitize_text_for_external_llm(normalized)
        ctx.masked_active_text = san_report.masked_text
        ctx.sanitization_report = san_report

        warnings_list: List[str] = []
        if len(normalized) < 15:
            warn_msg = "El texto es muy breve; puede carecer de contexto suficiente."
            warnings_list.append(warn_msg)
            ctx.warnings.append(warn_msg)

        return {
            "status": "ok",
            "is_valid": True,
            "input_mode": "text",
            "normalized_char_count": len(normalized),
            "masked_text_preview": ctx.masked_active_text[:500],
            "warnings": warnings_list,
            "error_code": None,
            "error_message": None,
        }

    elif requested_mode == "ocr_screenshot":
        if not ctx.image_bytes:
            ctx.is_input_valid = False
            ctx.validation_error_code = "EMPTY_IMAGE_BYTES"
            ctx.validation_error_message = "No se proporcionaron bytes de imagen para validar."
            return {
                "status": "invalid",
                "is_valid": False,
                "input_mode": "ocr_screenshot",
                "image_metadata": {},
                "warnings": [],
                "error_code": ctx.validation_error_code,
                "error_message": ctx.validation_error_message,
            }

        try:
            img = validate_and_load_image(ctx.image_bytes, ctx.image_filename)
            ctx.is_input_valid = True
            ctx.validated_image = img
            ctx.image_metadata = {
                "width": img.width,
                "height": img.height,
                "format": img.format or "RGB",
                "size_bytes": len(ctx.image_bytes),
            }
            return {
                "status": "ok",
                "is_valid": True,
                "input_mode": "ocr_screenshot",
                "image_metadata": ctx.image_metadata,
                "warnings": [],
                "error_code": None,
                "error_message": None,
            }
        except ImageValidationError as img_err:
            ctx.is_input_valid = False
            ctx.validation_error_code = "INVALID_IMAGE"
            ctx.validation_error_message = str(img_err)
            return {
                "status": "invalid",
                "is_valid": False,
                "input_mode": "ocr_screenshot",
                "image_metadata": {},
                "warnings": [],
                "error_code": ctx.validation_error_code,
                "error_message": ctx.validation_error_message,
            }
        except Exception as exc:
            ctx.is_input_valid = False
            ctx.validation_error_code = "VALIDATION_TOOL_ERROR"
            ctx.validation_error_message = f"Fallo inesperado al validar la imagen: {str(exc)}"
            return {
                "status": "tool_error",
                "is_valid": False,
                "input_mode": "ocr_screenshot",
                "image_metadata": {},
                "warnings": [],
                "error_code": ctx.validation_error_code,
                "error_message": ctx.validation_error_message,
            }

    else:
        ctx.is_input_valid = False
        ctx.validation_error_code = "UNSUPPORTED_INPUT_MODE"
        ctx.validation_error_message = f"Modalidad de entrada no soportada: '{requested_mode}'."
        return {
            "status": "invalid",
            "is_valid": False,
            "input_mode": requested_mode,
            "warnings": [],
            "error_code": ctx.validation_error_code,
            "error_message": ctx.validation_error_message,
        }


def execute_tool_extraer_texto_captura(
    ctx: PreparationSessionContext,
    raw_args: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Herramienta Python de la skill `extraer-texto-captura`.
    Ejecuta Tesseract OCR local sobre la imagen validada en la sesión.
    """
    validate_tool_arguments(
        tool_name="tool_extraer_texto_captura",
        args=raw_args,
        allowed_params={"preprocess": bool},
        required_params=[],
    )
    ctx.tools_called.append("tool_extraer_texto_captura")
    ctx.ocr_executed = True

    if ctx.input_mode != "ocr_screenshot":
        ctx.ocr_status = "tool_error"
        ctx.ocr_error_message = (
            "La herramienta 'tool_extraer_texto_captura' solo puede invocarse cuando input_mode es 'ocr_screenshot'."
        )
        return {
            "status": "tool_error",
            "extracted_text": "",
            "char_count": 0,
            "ocr_url_warnings": [],
            "error_message": ctx.ocr_error_message,
        }

    if not ctx.validation_done or not ctx.is_input_valid or ctx.validated_image is None:
        ctx.ocr_status = "tool_error"
        ctx.ocr_error_message = (
            "No hay una imagen validada en la sesión. Debe ejecutarse 'tool_validar_entrada' con éxito primero."
        )
        return {
            "status": "tool_error",
            "extracted_text": "",
            "char_count": 0,
            "ocr_url_warnings": [],
            "error_message": ctx.ocr_error_message,
        }

    ocr_service = ctx.ocr_service_override or get_ocr_service()
    if not ocr_service.is_available:
        ctx.ocr_status = "tool_error"
        ctx.ocr_error_message = (
            ocr_service.initialization_error
            or "El motor local Tesseract OCR no está disponible en el sistema."
        )
        return {
            "status": "tool_error",
            "extracted_text": "",
            "char_count": 0,
            "ocr_url_warnings": [],
            "error_message": ctx.ocr_error_message,
        }

    try:
        processed_img = preprocess_image_for_ocr(ctx.validated_image)
        ocr_res = ocr_service.extract_text(processed_img)

        if not ocr_res.get("success"):
            ctx.ocr_status = "tool_error"
            ctx.ocr_error_message = ocr_res.get("error") or "Fallo durante la ejecución de Tesseract OCR."
            return {
                "status": "tool_error",
                "extracted_text": "",
                "char_count": 0,
                "ocr_url_warnings": [],
                "error_message": ctx.ocr_error_message,
            }

        extracted_raw = normalize_text_content(ocr_res.get("text") or "")
        url_warns = ocr_res.get("ocr_url_warnings") or ocr_res.get("url_warnings") or []
        ctx.ocr_url_warnings = list(url_warns)
        for uw in url_warns:
            exp = uw.get("explanation")
            if exp and exp not in ctx.warnings:
                ctx.warnings.append(exp)

        if not extracted_raw or len(extracted_raw.strip()) < 3:
            ctx.ocr_status = "empty_or_illegible"
            ctx.raw_active_text = ""
            ctx.masked_active_text = ""
            ctx.ocr_error_message = (
                "No se pudo extraer texto legible de la captura de pantalla (imagen en blanco, borrosa o sin texto)."
            )
            ctx.warnings.append(ctx.ocr_error_message)
            return {
                "status": "empty_or_illegible",
                "extracted_text": "",
                "char_count": 0,
                "language_used": ocr_res.get("language_used", "spa"),
                "ocr_url_warnings": [],
                "error_message": ctx.ocr_error_message,
            }

        # Verificar límite máximo de caracteres en texto extraído
        policy = load_policy()
        max_chars = policy.get("runtime_constraints", {}).get("max_input_chars", 15000)
        if len(extracted_raw) > max_chars:
            extracted_raw = extracted_raw[:max_chars]
            ctx.warnings.append(f"El texto extraído por OCR fue truncado al límite de {max_chars} caracteres.")

        ctx.ocr_status = "ok"
        ctx.raw_active_text = extracted_raw
        san_report = sanitize_text_for_external_llm(extracted_raw)
        ctx.masked_active_text = san_report.masked_text
        ctx.sanitization_report = san_report

        return {
            "status": "ok",
            "extracted_text": ctx.masked_active_text,
            "char_count": len(extracted_raw),
            "language_used": ocr_res.get("language_used", "spa+eng"),
            "ocr_url_warnings": url_warns,
            "error_message": None,
        }

    except Exception as exc:
        ctx.ocr_status = "tool_error"
        ctx.ocr_error_message = f"Excepción inesperada en herramienta de OCR: {str(exc)}"
        return {
            "status": "tool_error",
            "extracted_text": "",
            "char_count": 0,
            "ocr_url_warnings": [],
            "error_message": ctx.ocr_error_message,
        }


def execute_tool_extraer_enlaces(
    ctx: PreparationSessionContext,
    raw_args: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Herramienta Python de la skill `extraer-enlaces`.
    Extrae y audita estáticamente las URLs en el texto activo de la sesión (Zero Network).
    """
    validate_tool_arguments(
        tool_name="tool_extraer_enlaces",
        args=raw_args,
        allowed_params={"include_static_metadata": bool},
        required_params=[],
    )
    ctx.tools_called.append("tool_extraer_enlaces")
    ctx.links_extracted = True

    if not ctx.raw_active_text.strip():
        return {
            "status": "no_links",
            "links_count": 0,
            "urls": [],
            "url_details": [],
            "warnings": ["No hay texto disponible en la sesión para buscar enlaces."],
            "error_message": None,
        }

    try:
        urls = extract_urls(ctx.raw_active_text)
        details = analyze_urls_in_text(ctx.raw_active_text)
        ctx.extracted_urls = list(urls)
        ctx.url_details = list(details)

        link_warnings: List[str] = []
        for d in details:
            for finding in d.get("findings", []):
                if "HTTPS" not in finding:  # Destacar anomalías reales como advertencia
                    w_str = f"URL [{d.get('domain')}]: {finding}"
                    link_warnings.append(w_str)
                    if w_str not in ctx.warnings:
                        ctx.warnings.append(w_str)

        return {
            "status": "ok" if urls else "no_links",
            "links_count": len(urls),
            "urls": urls,
            "url_details": details,
            "warnings": link_warnings,
            "error_message": None,
        }
    except Exception as exc:
        return {
            "status": "tool_error",
            "links_count": 0,
            "urls": [],
            "url_details": [],
            "warnings": [],
            "error_message": f"Error en la extracción estática de enlaces: {str(exc)}",
        }


def execute_tool_motor_deterministico(
    raw_text: str,
    input_mode: str = "text",
    precomputed_agent_indicators: Optional[List[Dict[str, Any]]] = None,
    precomputed_url_analyses: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Herramienta acotada para que el Agente Orquestador invoque el motor determinístico
    existente (`web/analysis_adapter.analyze_text`) una vez que la preparación y el
    análisis del mensaje finalizaron con estado 'correcto'.
    Recibe los hallazgos validados del Agente Analizador de Mensajes para evaluarlos
    sin reejecutar las 5 categorías ni duplicar puntuaciones.
    """
    return analyze_text(
        raw_text,
        input_mode=input_mode,
        precomputed_agent_indicators=precomputed_agent_indicators,
        precomputed_url_analyses=precomputed_url_analyses,
    )

