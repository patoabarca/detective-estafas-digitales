"""
Módulo de Clasificación Explicable de Riesgo.

Determina el nivel de riesgo (BAJO, MEDIO, ALTO o INDETERMINADO) mediante
reglas ponderadas, trazables y documentadas en la política de seguridad.
No utiliza probabilidades estadísticas arbitrarias ni opacas.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


class RiskClassifier:
    """
    Clasificador de riesgo basado en evidencia y ponderación explícita.
    """

    def __init__(self, policy: Dict[str, Any] | None = None) -> None:
        self.policy = policy or {}
        # Cargar pesos configurados con valores por defecto seguros
        weights = self.policy.get("weights", {})
        self.weight_prompt_injection = weights.get("prompt_injection_attempt", 45)
        self.weight_cred_harvesting = weights.get("credential_harvesting", 40)
        self.weight_banking_threat = weights.get("banking_threat_urgency", 35)
        self.weight_advance_fee = weights.get("advance_fee_fraud", 35)
        self.weight_suspicious_url = weights.get("suspicious_url", 30)
        self.weight_debin = weights.get("debin_or_transfer_trick", 30)
        self.weight_urgency = weights.get("urgency_generic", 15)
        self.weight_entity = weights.get("unverified_entity_impersonation", 15)

        thresholds = self.policy.get("thresholds", {})
        self.thresh_alto = thresholds.get("alto", 50)
        self.thresh_medio = thresholds.get("medio", 20)

    def classify(
        self,
        raw_text: str,
        text_analysis: Dict[str, Any],
        url_analyses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calcula el nivel de riesgo y genera la justificación basada en evidencia.
        """
        cleaned_text = raw_text.strip() if raw_text else ""

        # 1. Caso INDETERMINADO: texto vacío o insuficiente para un análisis responsable
        if not cleaned_text or len(cleaned_text) < 10:
            return {
                "level": "INDETERMINADO",
                "score": 0,
                "summary": "El texto proporcionado es inexistente o contiene información insuficiente para emitir una evaluación de riesgo responsable.",
                "activated_rules": ["REGLA-INDET: Longitud de texto insuficiente (< 10 caracteres)."],
            }

        score = 0
        activated_rules: List[str] = []
        indicators = text_analysis.get("indicators", [])

        # Mapeo de indicadores textuales a reglas ponderadas
        for ind in indicators:
            ind_id = ind.get("id")
            if ind_id == "SEC-PROMPT-INJECTION":
                score += self.weight_prompt_injection
                activated_rules.append(
                    f"REGLA-SEC-01 (+{self.weight_prompt_injection} pts): Detección de tentativa de evasión o manipulación del agente (Prompt Injection)."
                )
            elif ind_id == "FRA-CAPTURA-CREDENCIALES":
                score += self.weight_cred_harvesting
                activated_rules.append(
                    f"REGLA-FRA-01 (+{self.weight_cred_harvesting} pts): Solicitud directa de claves, tokens o factores de autenticación (OTP)."
                )
            elif ind_id == "ING-AMENAZA-BLOQUEO":
                score += self.weight_banking_threat
                activated_rules.append(
                    f"REGLA-ING-01 (+{self.weight_banking_threat} pts): Amenaza de bloqueo o suspensión inminente de cuenta/servicio."
                )
            elif ind_id == "FRA-PAGO-ANTICIPADO":
                score += self.weight_advance_fee
                activated_rules.append(
                    f"REGLA-FRA-02 (+{self.weight_advance_fee} pts): Esquema de pago anticipado (solicitud de dinero para liberar premio/paquete)."
                )
            elif ind_id == "FRA-PREMIO-INESPERADO":
                score += 25
                activated_rules.append(
                    "REGLA-FRA-03 (+25 pts): Notificación de premio extraordinario o sorteo no verificable."
                )
            elif ind_id == "FRA-DEBIN-ENGANOSO":
                score += self.weight_debin
                activated_rules.append(
                    f"REGLA-FRA-04 (+{self.weight_debin} pts): Maniobra de DEBIN o supuesta transferencia por error."
                )
            elif ind_id == "ING-URGENCIA-ARTIFICIAL":
                score += self.weight_urgency
                activated_rules.append(
                    f"REGLA-ING-02 (+{self.weight_urgency} pts): Presión temporal o urgencia artificial detectada."
                )
            elif ind_id == "SUP-SUPLANTACION-ENTIDAD":
                score += self.weight_entity
                activated_rules.append(
                    f"REGLA-SUP-01 (+{self.weight_entity} pts): Invocación de nombre institucional en contexto coercitivo o transaccional."
                )

        # Evaluación de URLs sospechosas
        for url_item in url_analyses:
            findings = url_item.get("findings", [])
            is_ip = url_item.get("is_ip_address", False)
            has_puny = url_item.get("has_punycode", False)
            has_userinfo = url_item.get("has_userinfo", False)

            # Subdominios engañosos o IP directa
            has_misleading_subdomain = any("Uso engañoso" in f or "términos engañosos" in f for f in findings)
            has_suspicious_tld = any("extensión de dominio de bajo costo" in f for f in findings)

            if is_ip:
                score += self.weight_suspicious_url
                activated_rules.append(
                    f"REGLA-URL-01 (+{self.weight_suspicious_url} pts): Enlace sospechoso apuntando a dirección IP numérica sin dominio."
                )
            if has_misleading_subdomain:
                score += self.weight_suspicious_url
                activated_rules.append(
                    f"REGLA-URL-02 (+{self.weight_suspicious_url} pts): Enlace con subdominio engañoso imitando una marca o portal de validación."
                )
            if has_puny:
                score += 25
                activated_rules.append(
                    "REGLA-URL-03 (+25 pts): Enlace con punycode o caracteres homóglifos (suplantación visual)."
                )
            if has_userinfo:
                score += 20
                activated_rules.append(
                    "REGLA-URL-04 (+20 pts): Enlace con credenciales embebidas (patrón user:pass@host)."
                )
            if has_suspicious_tld and not has_misleading_subdomain:
                score += 15
                activated_rules.append(
                    "REGLA-URL-05 (+15 pts): Enlace con extensión de dominio frecuentemente desechable."
                )

        # Limitar puntaje máximo a 100
        score = min(score, 100)

        # Determinación del nivel de riesgo
        # Condición de salto a ALTO:
        # - Puntaje >= thresh_alto (50)
        # - Presencia de Prompt Injection
        # - Combinación crítica: (Amenaza o Urgencia) + Credenciales + (URL o Subdominio)
        has_injection = text_analysis.get("prompt_injection_detected", False)
        has_cred = any(ind.get("id") == "FRA-CAPTURA-CREDENCIALES" for ind in indicators)
        has_threat = any(ind.get("id") == "ING-AMENAZA-BLOQUEO" for ind in indicators)
        has_urgency = any(ind.get("id") == "ING-URGENCIA-ARTIFICIAL" for ind in indicators)
        has_advance_fee = any(ind.get("id") == "FRA-PAGO-ANTICIPADO" for ind in indicators)
        has_debin = any(ind.get("id") == "FRA-DEBIN-ENGANOSO" for ind in indicators)
        has_bad_url = len(url_analyses) > 0 and any(
            u.get("is_ip_address")
            or any("Uso engañoso" in f or "bajo costo" in f or "términos engañosos" in f for f in u.get("findings", []))
            for u in url_analyses
        )

        critical_combo = (
            (has_threat and (has_cred or has_bad_url))
            or (has_cred and has_bad_url)
            or ((has_threat or has_urgency) and has_cred)
            or has_advance_fee
            or has_debin
        )

        if has_injection or score >= self.thresh_alto or critical_combo:
            level = "ALTO"
            summary = "Se detectaron múltiples indicadores concordantes con maniobras de fraude, captura indebida de credenciales, coerción o manipulación."
        elif score >= self.thresh_medio:
            level = "MEDIO"
            summary = "Se detectaron señales aisladas de alarma (urgencia, enlaces no verificados o menciones institucionales) que requieren precaución y validación."
        else:
            level = "BAJO"
            summary = "No se detectaron indicadores significativos conocidos de fraude o coerción. IMPORTANTE: La ausencia de señales no garantiza que el mensaje sea genuino."

        return {
            "level": level,
            "score": score,
            "summary": summary,
            "activated_rules": activated_rules,
        }
