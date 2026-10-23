"""
Módulo Generador de Informes (Estructurado y Accesible).

Genera tanto el informe estructurado JSON para consumo programático y auditoría,
como la explicación en lenguaje sencillo para usuarios finales sin conocimientos técnicos.
No almacena mensajes de usuarios ni incluye datos personales innecesarios.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Dict, List


class ReportGenerator:
    """
    Genera reportes de evaluación en formato JSON y Markdown accesible.
    """

    LIMITATIONS = [
        "El análisis es puramente estático y local; no se realizaron peticiones de red, DNS ni consultas WHOIS.",
        "La clasificación se basa en heurísticas y reglas documentadas sobre patrones conocidos.",
        "La ausencia de indicadores conocidos de fraude NO garantiza que el mensaje o enlace sea legítimo.",
        "No se analizan archivos ejecutables ni adjuntos binarios en este MVP.",
    ]

    @staticmethod
    def get_recommendations(risk_level: str, has_urls: bool, has_creds: bool) -> List[str]:
        """
        Retorna recomendaciones concretas y preventivas según el nivel de riesgo detectado.
        """
        recs: List[str] = []

        if risk_level in ("ALTO", "MEDIO"):
            if has_urls:
                recs.append("NO hagas clic en ninguno de los enlaces incluidos en el mensaje.")
            if has_creds:
                recs.append("NUNCA compartas contraseñas, tokens de seguridad, PIN ni códigos de 6 dígitos que te lleguen por SMS o WhatsApp.")
            recs.append("No respondas el mensaje ni continúes la comunicación por esa vía.")
            recs.append("Verificá la situación comunicándote directamente con la entidad oficial a través de sus canales públicos (sitio web oficial, teléfono en el dorso de la tarjeta o sucursal bancaria).")
            recs.append("Si sospechás que diste algún dato confidencial, cambiá inmediatamente tus claves desde otro dispositivo y comunicate con el área de fraudes de tu banco.")
        elif risk_level == "INDETERMINADO":
            recs.append("El mensaje no contiene suficiente información para evaluar su seguridad. Evitá compartir datos personales hasta verificar el remitente.")
        else:  # BAJO
            recs.append("Aunque no se detectaron señales evidentes de alarma, mantené siempre la precaución.")
            recs.append("Recordá que ningún organismo oficial ni banco solicita contraseñas por mensaje directo.")

        return recs

    def build_non_technical_explanation(
        self,
        risk_level: str,
        indicators: List[Dict[str, Any]],
        url_analyses: List[Dict[str, Any]],
        prompt_injection: bool,
    ) -> str:
        """
        Redacta una explicación en lenguaje claro, empático y comprensible para cualquier persona.
        """
        if risk_level == "INDETERMINADO":
            return (
                "No pudimos determinar la seguridad de este mensaje porque el texto es demasiado breve "
                "o no contiene suficiente información para emitir un juicio responsable."
            )

        if prompt_injection:
            return (
                "¡Cuidado especial! Este mensaje contiene frases diseñadas para manipular al asistente de seguridad "
                "o forzar la ejecución de acciones indebidas. Esto es una técnica agresiva que indica una clara intención maliciosa."
            )

        if risk_level == "ALTO":
            parts = [
                "Este mensaje presenta un RIESGO ALTO de ser una estafa o intento de engaño digital."
            ]
            has_threat = any(i.get("id") == "ING-AMENAZA-BLOQUEO" for i in indicators)
            has_cred = any(i.get("id") == "FRA-CAPTURA-CREDENCIALES" for i in indicators)
            has_fee = any(i.get("id") == "FRA-PAGO-ANTICIPADO" for i in indicators)

            if has_threat and has_cred:
                parts.append(
                    "Están utilizando la táctica del miedo y la urgencia (diciéndote que van a bloquear tu cuenta) "
                    "para que te asustes y entregues tus claves o códigos de seguridad en una página falsa."
                )
            elif has_fee:
                parts.append(
                    "Te prometen un premio, paquete o beneficio, pero te piden pagar una suma previa para liberarlo. "
                    "Esta es la clásica estafa del pago anticipado: el premio no existe y perderás el dinero transferido."
                )
            elif url_analyses:
                parts.append(
                    "El mensaje intenta conducirte a una dirección web sospechosa que no coincide con los sitios oficiales."
                )
            else:
                parts.append(
                    "Se encontraron múltiples señales típicas de manipulación psicológica y solicitudes de datos indebidas."
                )

            return " ".join(parts)

        if risk_level == "MEDIO":
            return (
                "El mensaje contiene algunas señales que llaman la atención (como apuro para tomar una decisión o "
                "enlaces no verificados). Antes de realizar cualquier acción, te sugerimos validar por fuera si el mensaje es auténtico."
            )

        # BAJO
        return (
            "No encontramos en el texto las frases típicas de estafas conocidas (como apuros, amenazas de bloqueo o pedidos de claves). "
            "De todos modos, recordá que ninguna herramienta automática puede darte una garantía del 100%, por lo que siempre debés actuar con cautela."
        )

    def generate_json_report(
        self,
        risk_data: Dict[str, Any],
        text_analysis: Dict[str, Any],
        url_analyses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Genera el reporte estructurado en formato diccionario compatible con config/result_schema.json.
        """
        level = risk_data.get("level", "INDETERMINADO")
        indicators = text_analysis.get("indicators", [])
        has_urls = len(url_analyses) > 0
        has_creds = any(i.get("id") == "FRA-CAPTURA-CREDENCIALES" for i in indicators)
        injection_detected = text_analysis.get("prompt_injection_detected", False)
        injection_details = text_analysis.get("prompt_injection_details", [])

        explanation = self.build_non_technical_explanation(
            level, indicators, url_analyses, injection_detected
        )
        recommendations = self.get_recommendations(level, has_urls, has_creds)

        return {
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "risk_assessment": {
                "level": level,
                "score": risk_data.get("score", 0),
                "summary": risk_data.get("summary", ""),
                "activated_rules": risk_data.get("activated_rules", []),
            },
            "indicators_detected": indicators,
            "url_analysis": url_analyses,
            "prompt_injection_detected": injection_detected,
            "prompt_injection_details": injection_details,
            "limitations": self.LIMITATIONS,
            "recommendations": recommendations,
            "non_technical_explanation": explanation,
        }

    def generate_human_readable_report(self, report_dict: Dict[str, Any]) -> str:
        """
        Genera el informe formateado en Markdown para fácil lectura del usuario o presentación académica.
        """
        risk = report_dict.get("risk_assessment", {})
        level = risk.get("level", "INDETERMINADO")
        score = risk.get("score", 0)

        badge_map = {
            "ALTO": "🔴 **RIESGO ALTO** (Peligro potencial detectado)",
            "MEDIO": "🟡 **RIESGO MEDIO** (Requiere atención y verificación)",
            "BAJO": "🟢 **RIESGO BAJO** (Sin señales evidentes de alarma)",
            "INDETERMINADO": "⚪ **RIESGO INDETERMINADO** (Información insuficiente)",
        }
        badge = badge_map.get(level, level)

        lines: List[str] = [
            "# 🛡️ Informe de Detective de Estafas Digitales",
            "",
            f"### Resultado de la Evaluación: {badge}",
            f"- **Puntaje de Severidad:** {score}/100",
            f"- **Fecha y Hora del Análisis:** `{report_dict.get('timestamp')}`",
            "",
            "## 🗣️ Explicación en Lenguaje Sencillo",
            f"> {report_dict.get('non_technical_explanation')}",
            "",
        ]

        # Alerta de Prompt Injection si ocurrió
        if report_dict.get("prompt_injection_detected"):
            lines.extend([
                "### ⚠️ Advertencia de Seguridad: Intento de Inyección de Instrucciones",
                "El mensaje evaluado intentó forzar al sistema a ejecutar comandos o cambiar su comportamiento.",
                "**El motor neutralizó esta tentativa y no ejecutó ninguna orden.**",
                "",
            ])

        # Señales e Indicadores detectados
        indicators = report_dict.get("indicators_detected", [])
        lines.append("## 🔍 Indicadores Detectados en el Mensaje")
        if not indicators:
            lines.append("*(No se identificaron patrones característicos de estafas conocidas)*\n")
        else:
            for ind in indicators:
                lines.append(f"- **[{ind.get('severity')}] {ind.get('description')}**")
                snippets = ind.get("evidence_snippets", [])
                if snippets:
                    quotes = ", ".join([f'"{s}"' for s in snippets])
                    lines.append(f"  - *Fragmento detectado:* {quotes}")
            lines.append("")

        # Análisis de URLs
        urls = report_dict.get("url_analysis", [])
        if urls:
            lines.append("## 🌐 Auditoría de Enlaces (Análisis Estático Seguro)")
            for u in urls:
                lines.append(f"- **Enlace extraído:** `{u.get('raw_url')}`")
                lines.append(f"  - Dominio identificado: `{u.get('domain')}`")
                lines.append(f"  - ¿Apunta a una dirección IP directa?: {'SÍ (Sospechoso)' if u.get('is_ip_address') else 'No'}")
                lines.append(f"  - ¿Utiliza Punycode / Homóglifos?: {'SÍ (Alerta de suplantación)' if u.get('has_punycode') else 'No'}")
                for f in u.get("findings", []):
                    lines.append(f"  - ⚠️ {f}")
            lines.append("")

        # Reglas activadas
        rules = risk.get("activated_rules", [])
        if rules:
            lines.append("## ⚖️ Trazabilidad de Reglas Activadas")
            for r in rules:
                lines.append(f"- {r}")
            lines.append("")

        # Recomendaciones
        lines.append("## 💡 Recomendaciones Preventivas")
        for rec in report_dict.get("recommendations", []):
            lines.append(f"1. {rec}")
        lines.append("")

        # Limitaciones
        lines.append("## 📌 Limitaciones del Análisis")
        for lim in report_dict.get("limitations", []):
            lines.append(f"- {lim}")
        lines.append("")

        return "\n".join(lines)
