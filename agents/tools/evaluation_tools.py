"""
Herramientas Python Autorizadas para el Agente Evaluador (Etapa 4).

Implementa las 6 herramientas vinculadas a sus respectivas skills:
1. `tool_reunir_hallazgos` -> Skill: `reunir-hallazgos`
2. `tool_calcular_puntaje` -> Skill: `calcular-puntaje`
3. `tool_asignar_nivel_riesgo` -> Skill: `asignar-nivel-riesgo`
4. `tool_explicar_resultado` -> Skill: `explicar-resultado`
5. `tool_recomendar_cuidados` -> Skill: `recomendar-cuidados`
6. `tool_generar_pdf` -> Skill: `generar-pdf`

Cumple con todos los requisitos de seguridad y contratos:
- Reutiliza el motor Python existente (`scripts/risk_classifier.py`, `scripts/analyzer.py`,
  `scripts/report_generator.py`, `web/pdf_exporter.py`).
- No altera reglas, pesos, umbrales ni la definición del puntaje heurístico.
- Cero conexiones de red para URLs.
- Deduplica hallazgos conservando procedencia y evidencia literal de cada enlace.
- El modelo NO inventa ni suma puntos: todo cálculo numérico es determinístico en Python.
- Un análisis incompleto nunca se convierte en RIESGO BAJO.
- Soporta invocación concurrente o en lote de herramientas sin requerir turnos redundantes del LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from analyzer import TextAnalyzer
    from report_generator import ReportGenerator
    from risk_classifier import RiskClassifier
    from worker import load_policy
except ImportError:
    from scripts.analyzer import TextAnalyzer
    from scripts.report_generator import ReportGenerator
    from scripts.risk_classifier import RiskClassifier
    from scripts.worker import load_policy

from agents.common.contracts import (
    ContractValidationError,
    EvaluationResult,
    MessageAnalysisResult,
    PreparationResult,
    UrlAnalysisResult,
    validate_tool_arguments,
)
from agents.common.privacy import (
    sanitize_snippets_for_external_llm,
    sanitize_text_for_external_llm,
    sanitize_url_for_external_llm,
)
from agents.tools.preparation_tools import PreparationSessionContext
from web.pdf_exporter import generate_pdf_report


@dataclass
class EvaluationSessionState:
    """
    Estado mutable local durante el ciclo de evaluación del Agente Evaluador.
    Persiste los datos consolidados entre los turnos de herramientas sin compartirlos
    con procesos externos ni permitir que el modelo los modifique directamente.
    """
    raw_text: str = ""
    input_mode: str = "text"
    prep_res: Optional[PreparationResult] = None
    msg_res: Optional[MessageAnalysisResult] = None
    url_res: Optional[UrlAnalysisResult] = None
    session_ctx: Optional[PreparationSessionContext] = None
    policy_override: Optional[Dict[str, Any]] = None
    analyzer_override: Optional[Any] = None

    # 1. Reunión de hallazgos
    findings_gathered: bool = False
    unified_indicators: List[Dict[str, Any]] = field(default_factory=list)
    unified_url_analyses: List[Dict[str, Any]] = field(default_factory=list)

    # 2. Cálculo de puntaje
    score_calculated: bool = False
    score: int = 0
    activated_rules: List[str] = field(default_factory=list)
    is_indeterminate: bool = False
    indeterminate_summary: str = ""

    # 3. Asignación de nivel de riesgo
    risk_level_assigned: bool = False
    level: str = "INDETERMINADO"
    summary: str = ""

    # 4. Explicación
    explanation_generated: bool = False
    explanation: str = ""

    # 5. Recomendaciones
    recommendations_generated: bool = False
    recommendations: List[str] = field(default_factory=list)

    # 6. Generación de PDF
    pdf_generated: bool = False
    pdf_filename: Optional[str] = None
    pdf_bytes: Optional[bytes] = None

    # Trazabilidad y advertencias
    warnings: List[str] = field(default_factory=list)
    tools_called: List[str] = field(default_factory=list)


def execute_tool_reunir_hallazgos(
    session_ctx: Optional[PreparationSessionContext],
    eval_state: EvaluationSessionState,
    args: Dict[str, Any],
    analyzer_override: Optional[Any] = None,
    policy_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Herramienta: `tool_reunir_hallazgos`.
    Reúne los resultados validados de ambos analistas y las advertencias del preparador,
    ejecutando en Python las verificaciones transversales (Prompt Injection y Suplantación)
    sin duplicar reglas ni perder evidencia ni procedencia de cada enlace.
    """
    validate_tool_arguments(
        tool_name="tool_reunir_hallazgos",
        args=args,
        allowed_params={"confirm_session": bool},
        required_params=["confirm_session"],
    )
    if not args.get("confirm_session"):
        raise ContractValidationError("El argumento 'confirm_session' debe ser true.")

    if "tool_reunir_hallazgos" not in eval_state.tools_called:
        eval_state.tools_called.append("tool_reunir_hallazgos")

    if eval_state.findings_gathered:
        return {
            "status": "ok",
            "total_indicators": len(eval_state.unified_indicators),
            "total_urls_analyzed": len(eval_state.unified_url_analyses),
            "indicators_summary": [
                {
                    "id": ind.get("id"),
                    "category": ind.get("category"),
                    "severity": ind.get("severity"),
                    "description": ind.get("description"),
                    "evidence_count": len(ind.get("evidence_snippets", [])),
                }
                for ind in eval_state.unified_indicators
            ],
            "url_summary": [
                {
                    "url_id": u.get("url_id", f"URL-{i+1}"),
                    "domain": u.get("domain", ""),
                    "has_ip": bool(u.get("has_ip")),
                    "has_punycode": bool(u.get("has_punycode")),
                    "findings_count": len(u.get("findings", [])),
                }
                for i, u in enumerate(eval_state.unified_url_analyses)
            ],
            "warnings_count": len(eval_state.warnings),
            "already_gathered": True,
        }

    if eval_state.findings_gathered:
        return {
            "status": "ok",
            "total_indicators": len(eval_state.unified_indicators),
            "total_urls_analyzed": len(eval_state.unified_url_analyses),
            "warnings_count": len(eval_state.warnings),
        }

    prep = eval_state.prep_res or (getattr(session_ctx, "last_preparation_result", None) if session_ctx else None)
    msg = eval_state.msg_res
    url = eval_state.url_res

    if prep is None:
        raise ContractValidationError("No se dispone del resultado de preparación en la sesión.")
    if msg is None:
        raise ContractValidationError("No se dispone del resultado del análisis de mensaje en la sesión.")

    policy = policy_override or eval_state.policy_override or load_policy()
    analyzer = analyzer_override or eval_state.analyzer_override or TextAnalyzer(policy)

    raw_text = eval_state.raw_text or prep.texto_extraido_o_recibido
    msg_indicators = [
        f.to_engine_indicator() if hasattr(f, "to_engine_indicator") else f
        for f in msg.senales_encontradas
    ]

    url_analyses_dict_list: List[Dict[str, Any]] = []
    if url is not None and url.intervino_agente:
        for u in url.enlaces_analizados:
            url_analyses_dict_list.append(u.to_dict())

    composed = analyzer.compose_analysis_from_agent_findings(
        text=raw_text,
        agent_indicators=msg_indicators,
    )

    eval_state.unified_indicators = composed["indicators"]
    eval_state.unified_url_analyses = url_analyses_dict_list

    for w in prep.advertencias:
        if w not in eval_state.warnings:
            eval_state.warnings.append(w)
    for w in msg.advertencias:
        if w not in eval_state.warnings:
            eval_state.warnings.append(w)
    if url is not None:
        for w in url.advertencias:
            if w not in eval_state.warnings:
                eval_state.warnings.append(w)

    eval_state.findings_gathered = True

    safe_indicators_summary = [
        {
            "id": ind.get("id"),
            "category": ind.get("category"),
            "severity": ind.get("severity"),
            "description": ind.get("description"),
            "evidence_count": len(ind.get("evidence_snippets", [])),
        }
        for ind in eval_state.unified_indicators
    ]

    safe_url_summary = [
        {
            "url_id": u.get("url_id", f"URL-{i+1}"),
            "domain": u.get("domain", ""),
            "has_ip": bool(u.get("has_ip")),
            "has_punycode": bool(u.get("has_punycode")),
            "findings_count": len(u.get("findings", [])),
        }
        for i, u in enumerate(eval_state.unified_url_analyses)
    ]

    return {
        "status": "ok",
        "total_indicators": len(eval_state.unified_indicators),
        "total_urls_analyzed": len(eval_state.unified_url_analyses),
        "indicators_summary": safe_indicators_summary,
        "url_summary": safe_url_summary,
        "warnings_count": len(eval_state.warnings),
    }


def execute_tool_calcular_puntaje(
    eval_state: EvaluationSessionState,
    args: Dict[str, Any],
    policy_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Herramienta: `tool_calcular_puntaje`.
    Ejecuta estrictamente en Python el cálculo del puntaje de severidad acumulada (0-100)
    y la lista de reglas activadas sobre los hallazgos reunidos.
    """
    validate_tool_arguments(
        tool_name="tool_calcular_puntaje",
        args=args,
        allowed_params={"confirm_gathered": bool},
        required_params=["confirm_gathered"],
    )
    if not args.get("confirm_gathered"):
        raise ContractValidationError("El argumento 'confirm_gathered' debe ser true.")

    if "tool_calcular_puntaje" not in eval_state.tools_called:
        eval_state.tools_called.append("tool_calcular_puntaje")

    if not eval_state.findings_gathered:
        raise ContractValidationError(
            "Orden de ejecución inválido: debe invocarse 'tool_reunir_hallazgos' antes de 'tool_calcular_puntaje'."
        )

    if eval_state.score_calculated:
        return {
            "status": "ok",
            "score": eval_state.score,
            "activated_rules": eval_state.activated_rules,
            "rules_count": len(eval_state.activated_rules),
            "is_indeterminate": eval_state.is_indeterminate,
            "already_calculated": True,
        }

    policy = policy_override or eval_state.policy_override or load_policy()
    classifier = RiskClassifier(policy)

    text_analysis = {
        "indicators": eval_state.unified_indicators,
        "prompt_injection_detected": any(
            ind.get("id") == "SEC-PROMPT-INJECTION" for ind in eval_state.unified_indicators
        ),
    }

    score_res = classifier.calculate_score(
        raw_text=eval_state.raw_text,
        text_analysis=text_analysis,
        url_analyses=eval_state.unified_url_analyses,
    )

    eval_state.score_calculated = True
    eval_state.score = score_res["score"]
    eval_state.activated_rules = list(score_res["activated_rules"])
    eval_state.is_indeterminate = bool(score_res.get("is_indeterminate", False))
    eval_state.indeterminate_summary = score_res.get("indeterminate_summary", "")

    return {
        "status": "ok",
        "score": eval_state.score,
        "activated_rules": eval_state.activated_rules,
        "rules_count": len(eval_state.activated_rules),
        "is_indeterminate": eval_state.is_indeterminate,
    }


def execute_tool_asignar_nivel_riesgo(
    eval_state: EvaluationSessionState,
    args: Dict[str, Any],
    policy_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Herramienta: `tool_asignar_nivel_riesgo`.
    Asigna en Python el nivel cualitativo (BAJO, MEDIO, ALTO o INDETERMINADO)
    aplicando los umbrales documentados y salvaguardas de seguridad.
    """
    validate_tool_arguments(
        tool_name="tool_asignar_nivel_riesgo",
        args=args,
        allowed_params={"confirm_scored": bool},
        required_params=["confirm_scored"],
    )
    if not args.get("confirm_scored"):
        raise ContractValidationError("El argumento 'confirm_scored' debe ser true.")

    if "tool_asignar_nivel_riesgo" not in eval_state.tools_called:
        eval_state.tools_called.append("tool_asignar_nivel_riesgo")

    if not eval_state.score_calculated:
        raise ContractValidationError(
            "Orden de ejecución inválido: debe invocarse 'tool_calcular_puntaje' antes de 'tool_asignar_nivel_riesgo'."
        )

    if eval_state.risk_level_assigned:
        return {
            "status": "ok",
            "level": eval_state.level,
            "score": eval_state.score,
            "summary": eval_state.summary,
            "already_assigned": True,
        }

    policy = policy_override or eval_state.policy_override or load_policy()
    classifier = RiskClassifier(policy)

    specialist_incomplete = False
    incomplete_reason = ""
    if eval_state.msg_res and eval_state.msg_res.estado != "correcto":
        specialist_incomplete = True
        incomplete_reason = f"Análisis de mensaje incompleto ({eval_state.msg_res.estado})."
    elif eval_state.url_res and eval_state.url_res.estado == "incompleto":
        specialist_incomplete = True
        incomplete_reason = f"Análisis de enlaces incompleto ({eval_state.url_res.detalle_estado})."

    is_indet = eval_state.is_indeterminate or specialist_incomplete
    summary_to_use = incomplete_reason or eval_state.indeterminate_summary

    text_analysis = {
        "indicators": eval_state.unified_indicators,
        "prompt_injection_detected": any(
            ind.get("id") == "SEC-PROMPT-INJECTION" for ind in eval_state.unified_indicators
        ),
    }

    level_res = classifier.assign_risk_level(
        score=eval_state.score,
        text_analysis=text_analysis,
        url_analyses=eval_state.unified_url_analyses,
        is_indeterminate=is_indet,
        indeterminate_summary=summary_to_use,
    )

    eval_state.risk_level_assigned = True
    eval_state.level = level_res["level"]
    eval_state.summary = level_res["summary"]

    return {
        "status": "ok",
        "level": eval_state.level,
        "score": eval_state.score,
        "summary": eval_state.summary,
    }


def execute_tool_explicar_resultado(
    eval_state: EvaluationSessionState,
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Herramienta: `tool_explicar_resultado`.
    Produce la explicación en lenguaje accesible y empático basada estrictamente
    en el nivel de riesgo asignado y las evidencias comprobadas.
    """
    validate_tool_arguments(
        tool_name="tool_explicar_resultado",
        args=args,
        allowed_params={"confirm_level_assigned": bool},
        required_params=["confirm_level_assigned"],
    )
    if not args.get("confirm_level_assigned"):
        raise ContractValidationError("El argumento 'confirm_level_assigned' debe ser true.")

    if "tool_explicar_resultado" not in eval_state.tools_called:
        eval_state.tools_called.append("tool_explicar_resultado")

    if not eval_state.risk_level_assigned:
        raise ContractValidationError(
            "Orden de ejecución inválido: debe invocarse 'tool_asignar_nivel_riesgo' antes de 'tool_explicar_resultado'."
        )

    if eval_state.explanation_generated:
        return {
            "status": "ok",
            "explanation": eval_state.explanation,
            "already_generated": True,
        }

    report_gen = ReportGenerator()
    has_injection = any(
        ind.get("id") == "SEC-PROMPT-INJECTION" for ind in eval_state.unified_indicators
    )

    explanation = report_gen.build_non_technical_explanation(
        risk_level=eval_state.level,
        indicators=eval_state.unified_indicators,
        url_analyses=eval_state.unified_url_analyses,
        prompt_injection=has_injection,
    )

    eval_state.explanation_generated = True
    eval_state.explanation = explanation

    return {
        "status": "ok",
        "explanation": eval_state.explanation,
    }


def execute_tool_recomendar_cuidados(
    eval_state: EvaluationSessionState,
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Herramienta: `tool_recomendar_cuidados`.
    Selecciona las recomendaciones preventivas del sistema acordes al nivel de riesgo
    y a la presencia de enlaces o solicitudes de datos sensibles.
    """
    validate_tool_arguments(
        tool_name="tool_recomendar_cuidados",
        args=args,
        allowed_params={"confirm_level_assigned": bool},
        required_params=["confirm_level_assigned"],
    )
    if not args.get("confirm_level_assigned"):
        raise ContractValidationError("El argumento 'confirm_level_assigned' debe ser true.")

    if "tool_recomendar_cuidados" not in eval_state.tools_called:
        eval_state.tools_called.append("tool_recomendar_cuidados")

    if not eval_state.risk_level_assigned:
        raise ContractValidationError(
            "Orden de ejecución inválido: debe invocarse 'tool_asignar_nivel_riesgo' antes de 'tool_recomendar_cuidados'."
        )

    if eval_state.recommendations_generated:
        return {
            "status": "ok",
            "recommendations_count": len(eval_state.recommendations),
            "recommendations": eval_state.recommendations,
            "source_category": "recomendaciones preventivas del sistema",
            "already_generated": True,
        }

    has_urls = len(eval_state.unified_url_analyses) > 0
    has_creds = any(
        ind.get("id") == "FRA-CAPTURA-CREDENCIALES" for ind in eval_state.unified_indicators
    )

    recs = ReportGenerator.get_recommendations(
        risk_level=eval_state.level,
        has_urls=has_urls,
        has_creds=has_creds,
    )

    eval_state.recommendations_generated = True
    eval_state.recommendations = list(recs)

    return {
        "status": "ok",
        "recommendations_count": len(eval_state.recommendations),
        "recommendations": eval_state.recommendations,
        "source_category": "recomendaciones preventivas del sistema",
    }


def execute_tool_generar_pdf(
    eval_state: EvaluationSessionState,
    args: Dict[str, Any],
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Herramienta: `tool_generar_pdf`.
    Renderiza la evaluación final validada en un flujo PDF en memoria mediante ReportLab
    y opcionalmente lo guarda en `output/` con un nombre controlado y protegido contra sobrescritura.
    Nunca envía los bytes binarios crudos al modelo de IA.
    """
    validate_tool_arguments(
        tool_name="tool_generar_pdf",
        args=args,
        allowed_params={"save_to_output": bool},
        required_params=[],
    )
    save_to_output = bool(args.get("save_to_output", False))

    if "tool_generar_pdf" not in eval_state.tools_called:
        eval_state.tools_called.append("tool_generar_pdf")

    if not eval_state.risk_level_assigned or not eval_state.explanation_generated or not eval_state.recommendations_generated:
        raise ContractValidationError(
            "Orden de ejecución inválido: debe completarse la evaluación antes de invocar 'tool_generar_pdf'."
        )

    if eval_state.pdf_generated and eval_state.pdf_bytes is not None:
        return {
            "status": "ok",
            "pdf_ready": True,
            "pdf_filename": eval_state.pdf_filename,
            "saved_to_disk": eval_state.pdf_filename is not None,
            "byte_size": len(eval_state.pdf_bytes),
            "already_generated": True,
        }

    has_injection = any(
        ind.get("id") == "SEC-PROMPT-INJECTION" for ind in eval_state.unified_indicators
    )
    injection_details = [
        snip
        for ind in eval_state.unified_indicators
        if ind.get("id") == "SEC-PROMPT-INJECTION"
        for snip in ind.get("evidence_snippets", [])
    ]

    report_dict: Dict[str, Any] = {
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "risk_assessment": {
            "level": eval_state.level,
            "score": eval_state.score,
            "score_type": "heuristic_severity_score",
            "score_disclaimer": "Puntaje heurístico acumulativo (0-100). No representa una probabilidad estadística de fraude.",
            "summary": eval_state.summary,
            "activated_rules": eval_state.activated_rules,
        },
        "indicators_detected": eval_state.unified_indicators,
        "url_analysis": eval_state.unified_url_analyses,
        "prompt_injection_detected": has_injection,
        "prompt_injection_details": injection_details,
        "limitations": ReportGenerator.LIMITATIONS,
        "recommendations": eval_state.recommendations,
        "non_technical_explanation": eval_state.explanation,
    }

    try:
        pdf_bytes = generate_pdf_report(report_dict)
    except Exception as pdf_exc:
        return {
            "status": "error",
            "error_type": "PDFGenerationError",
            "message": f"Fallo al renderizar PDF en memoria: {str(pdf_exc)[:120]}",
            "pdf_ready": False,
        }

    eval_state.pdf_generated = True
    eval_state.pdf_bytes = pdf_bytes

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    text_hash = hashlib.sha256(eval_state.raw_text.encode("utf-8")).hexdigest()[:6]
    controlled_filename = f"informe_detective_{ts}_{text_hash}.pdf"
    eval_state.pdf_filename = controlled_filename

    saved_to_disk = False
    if save_to_output:
        target_dir = output_dir or (PROJECT_ROOT / "output")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / controlled_filename
        target_path.write_bytes(pdf_bytes)
        saved_to_disk = True

    return {
        "status": "ok",
        "pdf_ready": True,
        "pdf_filename": controlled_filename,
        "saved_to_disk": saved_to_disk,
        "byte_size": len(pdf_bytes),
    }


def generate_pdf_from_evaluation_report(
    report_dict: Dict[str, Any],
    save_to_output: bool = False,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Función utilitaria directa para generar el PDF desde un reporte ya consolidado en la sesión
    de Streamlit, reutilizando 100% el código de `generar-pdf` sin invocar al modelo ni reanalizar.
    """
    pdf_bytes = generate_pdf_report(report_dict)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    text_content = report_dict.get("input_mode", "") + str(report_dict.get("risk_assessment", {}).get("score", 0))
    text_hash = hashlib.sha256(text_content.encode("utf-8")).hexdigest()[:6]
    controlled_filename = f"informe_detective_{ts}_{text_hash}.pdf"

    saved_to_disk = False
    saved_path = None
    if save_to_output:
        target_dir = output_dir or (PROJECT_ROOT / "output")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / controlled_filename
        target_path.write_bytes(pdf_bytes)
        saved_to_disk = True
        saved_path = str(target_path)

    return {
        "pdf_bytes": pdf_bytes,
        "filename": controlled_filename,
        "byte_size": len(pdf_bytes),
        "saved_to_disk": saved_to_disk,
        "saved_path": saved_path,
    }
