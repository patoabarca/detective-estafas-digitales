"""
Módulo de Exportación de Informes en Formato PDF (ReportLab).

Genera un documento PDF estructurado, profesional y explicable en memoria (BytesIO),
cumpliendo los siguientes principios de seguridad:
- Generación 100% en memoria (RAM), sin persistencia en disco ni archivos temporales.
- Desactivación estricta de hipervínculos clickeables en URLs sospechosas (texto plano).
- Inclusión de metadatos de auditoría, fecha/hora y advertencias sobre puntaje heurístico.
- Adecuado tratamiento tipográfico de caracteres en español (tildes, 'ñ' y signos de puntuación).
"""

from __future__ import annotations

import io
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# Paleta sobria de ciberseguridad
COLOR_NAVY = colors.HexColor("#0F172A")
COLOR_SLATE_BORDER = colors.HexColor("#CBD5E1")
COLOR_TEXT_MAIN = colors.HexColor("#1E293B")
COLOR_TEXT_MUTED = colors.HexColor("#64748B")
COLOR_BG_CARD = colors.HexColor("#F8FAFC")

# Colores de severidad
COLOR_ALTO_BG = colors.HexColor("#FEF2F2")
COLOR_ALTO_BORDER = colors.HexColor("#EF4444")
COLOR_ALTO_TEXT = colors.HexColor("#991B1B")

COLOR_MEDIO_BG = colors.HexColor("#FFFBEB")
COLOR_MEDIO_BORDER = colors.HexColor("#F59E0B")
COLOR_MEDIO_TEXT = colors.HexColor("#92400E")

COLOR_BAJO_BG = colors.HexColor("#ECFDF5")
COLOR_BAJO_BORDER = colors.HexColor("#10B981")
COLOR_BAJO_TEXT = colors.HexColor("#065F46")

COLOR_INDET_BG = colors.HexColor("#F3F4F6")
COLOR_INDET_BORDER = colors.HexColor("#9CA3AF")
COLOR_INDET_TEXT = colors.HexColor("#374151")


def generate_pdf_report(report_data: Dict[str, Any]) -> bytes:
    """
    Genera el informe en formato PDF a partir del diccionario de resultados del motor.

    Parámetros:
        report_data (dict): Diccionario emitido por worker.run_pipeline o analysis_adapter.

    Retorna:
        bytes: Flujo binario del archivo PDF generado en memoria.
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=36,
        bottomMargin=36,
        title="Informe Detective de Estafas Digitales",
        author="Diplomatura en IA - Detective de Estafas Digitales",
    )

    styles = getSampleStyleSheet()

    # Estilos tipográficos personalizados
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=COLOR_NAVY,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=COLOR_TEXT_MUTED,
    )
    h2_style = ParagraphStyle(
        "Heading2Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=COLOR_NAVY,
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=COLOR_TEXT_MAIN,
    )
    body_bold = ParagraphStyle(
        "BodyBold",
        parent=body_style,
        fontName="Helvetica-Bold",
    )
    badge_style = ParagraphStyle(
        "BadgeText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        alignment=1,  # Centrado
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=COLOR_TEXT_MUTED,
    )

    story = []

    # 1. Encabezado principal
    story.append(Paragraph("🛡️ Detective de Estafas Digitales", title_style))
    story.append(Paragraph("Informe Técnico y Explicable de Evaluación de Riesgo en Ciberseguridad", subtitle_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=COLOR_NAVY, spaceAfter=12))

    # 2. Metadatos de la evaluación
    timestamp = report_data.get("timestamp", "Fecha no especificada")
    input_mode = report_data.get("input_mode", "text")
    mode_label = "Captura de pantalla (OCR local)" if input_mode == "ocr_screenshot" else "Texto directo (Copiado/Pegado)"
    is_orchestrated = (
        "agent_orchestration" in report_data
        or report_data.get("execution_mode") == "agent_orchestrated"
    )
    exec_label = (
        "Orquesta de Agentes IA (API Gemini + herramientas locales)"
        if is_orchestrated
        else "Modo Local Determinístico (Sin Red)"
    )

    meta_table_data = [
        [
            Paragraph("<b>Fecha y Hora UTC:</b>", body_style),
            Paragraph(str(timestamp), body_style),
            Paragraph("<b>Modalidad de Entrada:</b>", body_style),
            Paragraph(mode_label, body_style),
        ],
        [
            Paragraph("<b>Modo de Ejecución:</b>", body_style),
            Paragraph(exec_label, body_style),
            Paragraph("<b>Análisis de Enlaces:</b>", body_style),
            Paragraph("Estático (sin visitas ni DNS/WHOIS)", body_style),
        ],
    ]
    meta_table = Table(meta_table_data, colWidths=[100, 160, 120, 150])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_CARD),
            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_SLATE_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # 3. Resultado de Evaluación y Nivel de Riesgo
    risk_info = report_data.get("risk_assessment", {})
    level = str(risk_info.get("level", "INDETERMINADO")).upper()
    score = risk_info.get("score", 0)

    if level == "ALTO":
        bg_col, border_col, text_col = COLOR_ALTO_BG, COLOR_ALTO_BORDER, COLOR_ALTO_TEXT
        badge_label = f"🔴 RIESGO ALTO (Puntaje Heurístico: {score}/100)"
    elif level == "MEDIO":
        bg_col, border_col, text_col = COLOR_MEDIO_BG, COLOR_MEDIO_BORDER, COLOR_MEDIO_TEXT
        badge_label = f"🟡 RIESGO MEDIO (Puntaje Heurístico: {score}/100)"
    elif level == "BAJO":
        bg_col, border_col, text_col = COLOR_BAJO_BG, COLOR_BAJO_BORDER, COLOR_BAJO_TEXT
        badge_label = f"🟢 RIESGO BAJO (Puntaje Heurístico: {score}/100)"
    else:
        bg_col, border_col, text_col = COLOR_INDET_BG, COLOR_INDET_BORDER, COLOR_INDET_TEXT
        badge_label = f"⚪ RIESGO INDETERMINADO (Puntaje Heurístico: {score}/100)"

    badge_style.textColor = text_col

    result_box_data = [
        [Paragraph(badge_label, badge_style)],
        [Paragraph(
            "<b>Aclaración Metodológica:</b> El puntaje es una medida heurística acumulativa de riesgo "
            "y no representa una probabilidad estadística de fraude. La ausencia de señales no garantiza que un mensaje sea genuino.",
            disclaimer_style,
        )],
    ]
    result_table = Table(result_box_data, colWidths=[530])
    result_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg_col),
            ("BOX", (0, 0), (-1, -1), 1.5, border_col),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ])
    )
    story.append(result_table)
    story.append(Spacer(1, 10))

    # 4. Explicación en lenguaje sencillo
    explanation = report_data.get("non_technical_explanation", risk_info.get("summary", "Sin descripción."))
    story.append(Paragraph("🗣️ Explicación en Lenguaje Accesible", h2_style))
    story.append(Paragraph(explanation, body_style))
    story.append(Spacer(1, 10))

    # 5. Indicadores Detectados en el Mensaje
    indicators = report_data.get("indicators_detected", [])
    story.append(Paragraph("🔍 Indicadores y Señales Detectadas", h2_style))

    if indicators:
        ind_rows = [
            [
                Paragraph("<b>Severidad</b>", body_bold),
                Paragraph("<b>Indicador / Categoría</b>", body_bold),
                Paragraph("<b>Fragmento Detectado</b>", body_bold),
                Paragraph("<b>Descripción del Riesgo</b>", body_bold),
            ]
        ]
        for ind in indicators:
            sev = ind.get("severity", "MEDIA")
            sev_badge = f"<b>[{sev}]</b>"
            snippets = ", ".join(f'"{s}"' for s in ind.get("evidence_snippets", []))
            ind_rows.append([
                Paragraph(sev_badge, body_style),
                Paragraph(f"{ind.get('id', '')}<br/><font color='#64748B'>{ind.get('category', '')}</font>", body_style),
                Paragraph(snippets or "Patrón contextual", body_style),
                Paragraph(ind.get("description", ""), body_style),
            ])

        ind_table = Table(ind_rows, colWidths=[65, 120, 145, 200])
        ind_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_BG_CARD),
                ("BOX", (0, 0), (-1, -1), 0.5, COLOR_SLATE_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, COLOR_SLATE_BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(ind_table)
    else:
        story.append(Paragraph("<i>No se identificaron patrones explícitos de fraude ni ingeniería social en el texto.</i>", body_style))

    story.append(Spacer(1, 10))

    # 6. Auditoría Estática de Enlaces (URLs)
    url_analyses = report_data.get("url_analysis", [])
    if url_analyses:
        story.append(Paragraph("🌐 Auditoría de Enlaces (Análisis Estático Seguro)", h2_style))
        story.append(Paragraph(
            "<b>Nota de Aislamiento:</b> Las direcciones se muestran como texto plano no clickeable. "
            "El análisis de enlaces es estático: no se visitaron las URLs ni se realizaron consultas DNS o WHOIS.",
            disclaimer_style,
        ))
        story.append(Spacer(1, 4))

        for item in url_analyses:
            raw_url = item.get("raw_url", "")
            domain = item.get("domain", "")
            findings = item.get("findings", [])

            url_box_data = [
                [Paragraph("<b>Enlace inspeccionado:</b>", body_bold), Paragraph(f"<code>{raw_url}</code>", body_style)],
                [Paragraph("<b>Dominio extraído:</b>", body_bold), Paragraph(f"<b>{domain}</b>", body_style)],
            ]
            if findings:
                finding_items = "".join(f"<li>{f}</li>" for f in findings)
                url_box_data.append([
                    Paragraph("<b>Hallazgos:</b>", body_bold),
                    Paragraph(f"<ul>{finding_items}</ul>", body_style),
                ])

            url_tbl = Table(url_box_data, colWidths=[120, 410])
            url_tbl.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_CARD),
                    ("BOX", (0, 0), (-1, -1), 0.5, COLOR_SLATE_BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ])
            )
            story.append(url_tbl)
            story.append(Spacer(1, 6))

    # 7. Recomendaciones Preventivas
    recs = report_data.get("recommendations", [])
    if recs:
        story.append(Paragraph("💡 Recomendaciones Preventivas", h2_style))
        rec_items = "".join(f"<li>{r}</li>" for r in recs)
        story.append(Paragraph(f"<ol>{rec_items}</ol>", body_style))
        story.append(Spacer(1, 10))

    # 8. Limitaciones y Advertencia de Responsabilidad
    limits = report_data.get("limitations", [])
    story.append(Paragraph("📌 Limitaciones del Sistema", h2_style))
    limit_items = "".join(f"<li>{lim}</li>" for lim in limits)
    story.append(Paragraph(f"<ul>{limit_items}</ul>", disclaimer_style))

    # Construir PDF en memoria
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
