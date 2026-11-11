"""
Módulo de Componentes Visuales y Estilos UI para Streamlit.

Proporciona estilos CSS refinados, tarjetas accesibles y renderizadores
para presentar los informes de forma profesional, clara y adaptable
a dispositivos móviles y de escritorio.
"""

from __future__ import annotations

from typing import Any, Dict, List
import streamlit as st


# =============================================================================
# Inyección de Estilos CSS Personalizados
# =============================================================================

CUSTOM_CSS = """
<style>
/* Tipografía y espaciado general */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

/* Encabezado Principal */
.main-header {
    background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
    color: #F8FAFC;
    padding: 2rem 2.2rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    border-left: 6px solid #38BDF8;
}

.main-header h1 {
    color: #F8FAFC !important;
    font-size: 2.1rem;
    font-weight: 700;
    margin: 0 0 0.5rem 0;
    display: flex;
    align-items: center;
    gap: 0.6rem;
}

.main-header p.subtitle {
    color: #94A3B8;
    font-size: 1.1rem;
    margin: 0 0 0.8rem 0;
    font-weight: 400;
}

.main-header .disclaimer {
    background: rgba(255, 255, 255, 0.08);
    border-left: 3px solid #38BDF8;
    padding: 0.6rem 0.9rem;
    border-radius: 4px;
    font-size: 0.85rem;
    color: #CBD5E1;
    margin-top: 0.5rem;
}

/* Tarjetas de Evaluación de Riesgo */
.risk-card {
    border-radius: 10px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.risk-card-alto {
    background-color: #FEF2F2;
    border: 2px solid #EF4444;
    border-left: 8px solid #DC2626;
}

.risk-card-medio {
    background-color: #FFFBEB;
    border: 2px solid #F59E0B;
    border-left: 8px solid #D97706;
}

.risk-card-bajo {
    background-color: #ECFDF5;
    border: 2px solid #10B981;
    border-left: 8px solid #059669;
}

.risk-card-indet {
    background-color: #F3F4F6;
    border: 2px solid #9CA3AF;
    border-left: 8px solid #4B5563;
}

.risk-title {
    font-size: 1.4rem;
    font-weight: 700;
    margin-bottom: 0.4rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.risk-title-alto { color: #991B1B; }
.risk-title-medio { color: #92400E; }
.risk-title-bajo { color: #065F46; }
.risk-title-indet { color: #374151; }

.risk-score {
    font-size: 1rem;
    font-weight: 600;
    color: #475569;
    margin-bottom: 0.6rem;
}

.heuristic-disclaimer {
    font-size: 0.85rem;
    color: #64748B;
    font-style: italic;
    margin-top: 0.4rem;
}

/* Tarjetas de Indicadores */
.indicator-card {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-left: 4px solid #64748B;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.indicator-card-critica { border-left-color: #DC2626; }
.indicator-card-alta { border-left-color: #EA580C; }
.indicator-card-media { border-left-color: #D97706; }
.indicator-card-baja { border-left-color: #059669; }

.indicator-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.4rem;
}

.indicator-name {
    font-weight: 600;
    font-size: 1rem;
    color: #1E293B;
}

.severity-pill {
    font-size: 0.75rem;
    font-weight: 700;
    padding: 0.2rem 0.5rem;
    border-radius: 9999px;
    text-transform: uppercase;
}

.pill-critica { background-color: #FEE2E2; color: #991B1B; }
.pill-alta { background-color: #FFEDD5; color: #9A3412; }
.pill-media { background-color: #FEF3C7; color: #92400E; }
.pill-baja { background-color: #D1FAE5; color: #065F46; }

.evidence-quote {
    background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 4px;
    padding: 0.35rem 0.6rem;
    font-family: monospace;
    font-size: 0.9rem;
    color: #334155;
    margin: 0.4rem 0;
    display: inline-block;
}

/* Tarjeta de URLs */
.url-card {
    background-color: #F8FAFC;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 1.1rem 1.3rem;
    margin-bottom: 1rem;
}

.url-raw-text {
    font-family: "Courier New", Courier, monospace;
    font-size: 0.95rem;
    background-color: #0F172A;
    color: #38BDF8;
    padding: 0.4rem 0.8rem;
    border-radius: 4px;
    display: block;
    word-break: break-all;
    user-select: all;
    margin-bottom: 0.6rem;
}

/* Advertencia OCR en URLs */
.ocr-url-alert {
    background-color: #FEF3C7;
    border: 1px solid #F59E0B;
    border-left: 5px solid #D97706;
    border-radius: 6px;
    padding: 0.8rem 1rem;
    margin-bottom: 1rem;
    color: #92400E;
    font-size: 0.9rem;
}
</style>
"""


def apply_custom_styles() -> None:
    """Aplica la hoja de estilos personalizada a la página de Streamlit."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_header() -> None:
    """Renderiza el banner y encabezado principal de la aplicación."""
    st.markdown(
        """
        <div class="main-header">
            <h1>🛡️ Detective de Estafas Digitales</h1>
            <p class="subtitle">¿Recibiste un mensaje sospechoso? Analizalo antes de confiar.</p>
            <div class="disclaimer">
                ℹ️ <b>Aviso de Responsabilidad:</b> Esta herramienta ayuda a identificar señales de posibles
                estafas y maniobras de ingeniería social. Sus resultados son orientativos y no garantizan
                la legitimidad absoluta de un mensaje.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_risk_card(risk_data: Dict[str, Any]) -> None:
    """Renderiza la tarjeta principal con el resultado de riesgo y puntaje heurístico."""
    level = str(risk_data.get("level", "INDETERMINADO")).upper()
    score = risk_data.get("score", 0)

    if level == "ALTO":
        card_class = "risk-card-alto"
        title_class = "risk-title-alto"
        icon = "🔴"
        label = "RIESGO ALTO"
        summary = (
            "Se detectaron múltiples indicadores concordantes con maniobras de fraude, "
            "captura indebida de credenciales, coerción o enlaces engañosos."
        )
    elif level == "MEDIO":
        card_class = "risk-card-medio"
        title_class = "risk-title-medio"
        icon = "🟡"
        label = "RIESGO MEDIO"
        summary = (
            "Se detectaron señales aisladas de alarma (urgencia, enlaces no verificados o "
            "menciones institucionales) que requieren precaución y validación antes de actuar."
        )
    elif level == "BAJO":
        card_class = "risk-card-bajo"
        title_class = "risk-title-bajo"
        icon = "🟢"
        label = "RIESGO BAJO"
        summary = (
            "No se detectaron indicadores significativos conocidos de fraude en el texto analizado. "
            "<b>Importante:</b> La ausencia de señales no garantiza que el mensaje sea genuino."
        )
    else:
        card_class = "risk-card-indet"
        title_class = "risk-title-indet"
        icon = "⚪"
        label = "RIESGO INDETERMINADO"
        summary = "El texto proporcionado es insuficiente para emitir una evaluación de riesgo responsable."

    st.markdown(
        f"""
        <div class="risk-card {card_class}">
            <div class="risk-title {title_class}">
                {icon} Resultado: {label}
            </div>
            <div class="risk-score">
                📊 Puntaje de Severidad Heurística: <b>{score}/100</b>
            </div>
            <div style="font-size: 0.95rem; color: #1E293B; line-height: 1.45;">
                {summary}
            </div>
            <div class="heuristic-disclaimer">
                ⚠️ El puntaje es una medida heurística acumulativa de riesgo y no representa una probabilidad estadística de fraude.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_indicators(indicators: List[Dict[str, Any]]) -> None:
    """Renderiza la lista de indicadores detectados en formato de tarjetas detalladas."""
    if not indicators:
        st.info("ℹ️ No se identificaron patrones explícitos de fraude ni ingeniería social en el texto analizado.")
        return

    st.markdown("### 🔍 Indicadores Detectados en el Mensaje")
    for ind in indicators:
        sev = str(ind.get("severity", "MEDIA")).lower()
        pill_class = f"pill-{sev}"
        card_class = f"indicator-card-{sev}"

        snippets = ind.get("evidence_snippets", [])
        snippets_html = ""
        if snippets:
            snippets_html = " ".join(f'<span class="evidence-quote">"{s}"</span>' for s in snippets)

        st.markdown(
            f"""
            <div class="indicator-card {card_class}">
                <div class="indicator-header">
                    <span class="indicator-name">🚨 {ind.get('description', '')}</span>
                    <span class="severity-pill {pill_class}">Severidad: {sev.upper()}</span>
                </div>
                <div style="font-size: 0.88rem; color: #64748B; margin-bottom: 0.3rem;">
                    Regla: <code>{ind.get('id', '')}</code> • Categoría: <b>{ind.get('category', '')}</b>
                </div>
                {f'<div style="margin-top: 0.4rem;"><small style="color: #475569;">Fragmento detectado:</small><br/>{snippets_html}</div>' if snippets_html else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_url_audit(url_analyses: List[Dict[str, Any]]) -> None:
    """Renderiza el desglose de auditoría estática de enlaces encontrados."""
    if not url_analyses:
        return

    st.markdown("### 🌐 Auditoría de Enlaces (Análisis Estático Seguro)")
    st.caption(
        "🔒 **Enlaces no visitados (análisis estático):** Las direcciones se muestran como texto plano no clickeable. "
        "No se visitaron las URLs ni se realizaron consultas DNS, WHOIS ni descargas hacia esos servidores."
    )

    for item in url_analyses:
        raw_url = item.get("raw_url", "")
        domain = item.get("domain", "")
        findings = item.get("findings", [])

        findings_html = "".join(f"<li>{f}</li>" for f in findings) if findings else "<li>No se observaron anomalías sintácticas evidentes.</li>"

        st.markdown(
            f"""
            <div class="url-card">
                <div style="font-size: 0.85rem; color: #64748B; margin-bottom: 0.2rem;">Enlace detectado (texto plano aislado):</div>
                <div class="url-raw-text">{raw_url}</div>
                <div style="font-size: 0.9rem; margin-bottom: 0.4rem;">
                    Dominio principal identificado: <b>{domain}</b>
                </div>
                <div style="font-size: 0.88rem; color: #334155;">
                    <b>Hallazgos del análisis sintáctico:</b>
                    <ul style="margin-top: 0.3rem; padding-left: 1.2rem;">
                        {findings_html}
                    </ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_ocr_url_warnings(warnings: List[Dict[str, str]]) -> None:
    """Muestra advertencias al usuario si el OCR parece haber distorsionado una URL."""
    if not warnings:
        return

    warning_list = "".join(
        f"<li><b>{w.get('snippet', '')}:</b> {w.get('explanation', '')}</li>" for w in warnings
    )
    st.markdown(
        f"""
        <div class="ocr-url-alert">
            ⚠️ <b>Atención con posibles errores del OCR en enlaces web:</b>
            <p style="margin: 0.3rem 0;">
                El reconocimiento óptico puede confundir caracteres en URLs (como letras 'l' por números '1',
                ceros por letras 'o', o comas por puntos). Verificá cuidadosamente el texto antes de analizar:
            </p>
            <ul style="margin: 0.3rem 0; padding-left: 1.2rem;">
                {warning_list}
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
