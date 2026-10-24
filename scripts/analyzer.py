"""
Módulo de Análisis de Indicadores Textuales e Ingeniería Social.

Este módulo analiza el contenido textual de mensajes para identificar
patrones de phishing, coerción, premios falsos, solicitudes de credenciales
y neutralizar tentativas de inyección de instrucciones (Prompt Injection).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


class TextAnalyzer:
    """
    Analizador determinístico y explicable de patrones textuales.
    Utiliza expresiones regulares y análisis contextual para evitar
    falsos positivos basados en palabras clave aisladas.
    """

    def __init__(self, policy: Dict[str, Any] | None = None) -> None:
        self.policy = policy or {}

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Ejecuta el análisis integral del texto.
        Retorna los indicadores detectados y la auditoría de seguridad de inyección.
        """
        if not text:
            return {
                "indicators": [],
                "prompt_injection_detected": False,
                "prompt_injection_details": [],
                "entity_mentions": [],
            }

        indicators: List[Dict[str, Any]] = []

        # 1. Detección de Intentos de Prompt Injection / Modificación de Contexto
        injection_detected, injection_snippets = self._detect_prompt_injection(text)
        if injection_detected:
            indicators.append({
                "id": "SEC-PROMPT-INJECTION",
                "category": "seguridad_ia",
                "severity": "CRITICA",
                "description": "El mensaje contiene directivas diseñadas para manipular, secuestrar o eludir las instrucciones del agente de IA (Prompt Injection).",
                "evidence_snippets": injection_snippets,
            })

        # 2. Detección de Amenazas de Bloqueo o Suspensión
        threat_detected, threat_snippets = self._detect_blocking_threats(text)
        if threat_detected:
            indicators.append({
                "id": "ING-AMENAZA-BLOQUEO",
                "category": "ingenieria_social",
                "severity": "ALTA",
                "description": "Amenaza explícita de bloqueo, suspensión o consecuencias negativas sobre una cuenta o servicio.",
                "evidence_snippets": threat_snippets,
            })

        # 3. Detección de Urgencia Artificial
        urgency_detected, urgency_snippets = self._detect_urgency(text)
        if urgency_detected:
            indicators.append({
                "id": "ING-URGENCIA-ARTIFICIAL",
                "category": "ingenieria_social",
                "severity": "MEDIA",
                "description": "Inducción deliberada de prisa temporal para forzar una decisión sin reflexión.",
                "evidence_snippets": urgency_snippets,
            })

        # 4. Solicitud de Credenciales y Factores de Autenticación
        cred_detected, cred_snippets = self._detect_credential_harvesting(text)
        if cred_detected:
            indicators.append({
                "id": "FRA-CAPTURA-CREDENCIALES",
                "category": "captura_datos",
                "severity": "ALTA",
                "description": "Solicitud de datos confidenciales (contraseñas, tokens de seguridad, códigos de 6 dígitos o PIN).",
                "evidence_snippets": cred_snippets,
            })

        # 5. Premios Inesperados y Promociones Extraordinarias
        reward_detected, reward_snippets = self._detect_fake_rewards(text)
        if reward_detected:
            indicators.append({
                "id": "FRA-PREMIO-INESPERADO",
                "category": "fraude_financiero",
                "severity": "ALTA",
                "description": "Promesa de premios no solicitados, sorteos no comprobables o bonos extraordinarios.",
                "evidence_snippets": reward_snippets,
            })

        # 6. Fraude de Pago Anticipado (Advance Fee Fraud)
        advance_detected, advance_snippets = self._detect_advance_fee(text)
        if advance_detected:
            indicators.append({
                "id": "FRA-PAGO-ANTICIPADO",
                "category": "fraude_financiero",
                "severity": "ALTA",
                "description": "Exigencia de abonar una tasa previa, seguro postal, o gasto administrativo para liberar un premio o paquete.",
                "evidence_snippets": advance_snippets,
            })

        # 7. Engaño de DEBIN o Transferencia Inversa
        debin_detected, debin_snippets = self._detect_debin_trick(text)
        if debin_detected:
            indicators.append({
                "id": "FRA-DEBIN-ENGANOSO",
                "category": "fraude_financiero",
                "severity": "ALTA",
                "description": "Mención de DEBIN o transferencias por error orientadas a extraer fondos de la víctima.",
                "evidence_snippets": debin_snippets,
            })

        # 8. Suplantación Contextual de Entidades
        entity_detected, entity_snippets, entities = self._detect_entity_impersonation(
            text, threat_detected or cred_detected or advance_detected or reward_detected
        )
        if entity_detected:
            indicators.append({
                "id": "SUP-SUPLANTACION-ENTIDAD",
                "category": "suplantacion",
                "severity": "MEDIA",
                "description": f"Mención de entidades oficiales o financieras ({', '.join(entities)}) en combinación con solicitudes de acción o amenazas.",
                "evidence_snippets": entity_snippets,
            })

        return {
            "indicators": indicators,
            "prompt_injection_detected": injection_detected,
            "prompt_injection_details": injection_snippets,
            "entity_mentions": entities,
        }

    # =========================================================================
    # Reglas y Expresiones Regulares Especializadas
    # =========================================================================

    def _detect_prompt_injection(self, text: str) -> Tuple[bool, List[str]]:
        patterns = [
            r"(?i)\b(?:ignora|ignor[aá]|olvida|descart[aá])\s+(?:todas\s+las\s+|las\s+)?instrucciones(?:\s+anteriores)?\b",
            r"(?i)\b(?:ignore|forget|disregard)\s+(?:all\s+)?(?:previous\s+)?instructions\b",
            r"(?i)\b(?:modo\s+(?:mantenimiento|depuraci[oó]n|dios|dan|root|admin)|jailbreak|dan\s+mode)\b",
            r"(?i)\b(?:ejecut[aá]|run|execute)\s+(?:un\s+)?(?:comando|powershell|bash|cmd|shell|script)\b",
            r"(?i)\b(?:revel[aá]|mostr[aá]|show|display|reveal)\s+(?:tus\s+|las\s+)?(?:claves|contrase[ñn]as|tokens|system\s+prompt|\.env)\b",
            r"(?i)\bno\s+menciones\s+(?:nada\s+de\s+)?este\s+mensaje\s+al\s+usuario\b",
            r"(?i)\ba\s+partir\s+de\s+ahora\s+sos\s+(?:un|una)\b",
        ]
        snippets: List[str] = []
        for pat in patterns:
            for match in re.finditer(pat, text):
                snippets.append(match.group(0).strip())
        return len(snippets) > 0, snippets

    def _detect_blocking_threats(self, text: str) -> Tuple[bool, List[str]]:
        patterns = [
            r"(?i)\b(?:cuenta(?:\s+bancaria)?|acceso|tarjeta|servicio)\s+(?:ser[aá]\s+)?(?:suspendid[oa]|bloquead[oa]|cancelad[oa]|inhabilitad[oa])\b",
            r"(?i)\b(?:bloqueo|suspensi[oó]n|inhabilitaci[oó]n)\s+(?:inmediat[oa]|preventiv[oa]|definitiv[oa])\b",
            r"(?i)\b(?:actividad\s+sospechosa|actividad\s+inusual|acceso\s+no\s+autorizado|inicio\s+de\s+sesi[oó]n\s+sospechoso)\b",
            r"(?i)\b(?:evit(?:ar|e)|para\s+evitar)\s+(?:el\s+bloqueo|la\s+suspensi[oó]n|el\s+cierre)\b",
            r"(?i)\b[uú]ltimo\s+aviso\s+antes\s+de\b",
        ]
        snippets: List[str] = []
        for pat in patterns:
            for match in re.finditer(pat, text):
                snippets.append(match.group(0).strip())
        return len(snippets) > 0, snippets

    def _detect_urgency(self, text: str) -> Tuple[bool, List[str]]:
        patterns = [
            r"(?i)\b(?:en\s+las\s+pr[oó]ximas\s+\d{1,2}\s+(?:horas|hs|minutos|min))\b",
            r"(?i)\b(?:plazo\s+de\s+\d{1,2}\s+(?:horas|hs))\b",
            r"(?i)\b(?:antes\s+de\s+las\s+\d{1,2}(?::\d{2})?\s*(?:hs|horas)?)\b",
            r"(?i)\b(?:de\s+forma\s+urgente|urgente|inmediatamente|a\s+la\s+brevedad|plazo\s+l[ií]mite)\b",
            r"(?i)\b(?:quedan\s+\d{1,2}\s+minutos|tiempo\s+l[ií]mite)\b",
            r"(?i)\b(?:(?:bloquead[oa]|suspendid[oa]|vence)\s+hoy|solo\s+por\s+hoy|hoy\s+mismo)\b",
        ]
        snippets: List[str] = []
        for pat in patterns:
            for match in re.finditer(pat, text):
                snippets.append(match.group(0).strip())
        return len(snippets) > 0, snippets

    def _detect_credential_harvesting(self, text: str) -> Tuple[bool, List[str]]:
        patterns = [
            r"(?i)\b(?:token\s+de\s+seguridad|clave\s+digital|clave\s+de\s+home\s+banking)\b",
            r"(?i)\b(?:c[oó]digo\s+de\s+(?:seguridad|verificaci[oó]n|\d+\s+d[ií]gitos))\b",
            r"(?i)\b(?:reingresar|reingres[ae]|ingresar|ingres[ae]|confirmar|confirm[ae]|validar|valid[ae]|actualizar|actualic[ee]|solicitar|solicit[ae]|compartir|compart[ae]|enviar|env[ií][ae]|pedir|pid[ae])\s+(?:su\s+|tu\s+)?(?:usuario|clave|documento|contrase[ñn]a|token|pin|c[oó]digo)\b",
            r"(?i)\b(?:pin\s+de\s+cajero|tarjeta\s+de\s+coordenadas)\b",
            r"(?i)\b(?:enlace\s+para\s+verificar\s+(?:su\s+)?identidad)\b",
            r"(?i)\b(?:solicitud\s+de\s+(?:su\s+)?(?:clave|contrase[ñn]a|token))\b",
        ]
        snippets: List[str] = []
        for pat in patterns:
            for match in re.finditer(pat, text):
                snippets.append(match.group(0).strip())
        return len(snippets) > 0, snippets

    def _detect_fake_rewards(self, text: str) -> Tuple[bool, List[str]]:
        patterns = [
            r"(?i)\b(?:fuiste\s+seleccionad[oa]|has\s+sido\s+seleccionad[oa]|ganador\s+del\s+sorteo|felicidades\s+ganaste)\b",
            r"(?i)\b(?:ganaste\s+(?:un[a]?\s+)?(?:iphone|smart\s*tv|playstation|auto|moto|\$\s*[\d\.]+))\b",
            r"(?i)\b(?:orden\s+de\s+compra\s+por\s+\$\s*[\d\.]+)\b",
            r"(?i)\b(?:bono\s+extraordinario|cobro\s+del\s+ife|beneficio\s+exclusivo\s+disponible)\b",
            r"(?i)\b(?:sorteo\s+aniversario|premio\s+millonario)\b",
        ]
        snippets: List[str] = []
        for pat in patterns:
            for match in re.finditer(pat, text):
                snippets.append(match.group(0).strip())
        return len(snippets) > 0, snippets

    def _detect_advance_fee(self, text: str) -> Tuple[bool, List[str]]:
        patterns = [
            r"(?i)\b(?:abonar|pagar|transferir|abon[aá]|transfer[ií])\s+(?:la\s+)?(?:tasa|seguro\s+postal|estampillado|gastos\s+administrativos|arancel|flete)\b",
            r"(?i)\b(?:para\s+coordinar\s+la\s+entrega|para\s+liberar\s+el\s+(?:premio|paquete|env[ií]o))\s+(?:deb[eé]s|debe|abon[aá]|pag[aá])\b",
            r"(?i)\b(?:tasa\s+de\s+aduana|estampillado\s+oficial|seguro\s+de\s+env[ií]o)\b",
            r"(?i)\b(?:si\s+no\s+realiz[aá]s\s+el\s+pago\s+el\s+premio\s+pasar[aá])\b",
        ]
        snippets: List[str] = []
        for pat in patterns:
            for match in re.finditer(pat, text):
                snippets.append(match.group(0).strip())
        return len(snippets) > 0, snippets

    def _detect_debin_trick(self, text: str) -> Tuple[bool, List[str]]:
        patterns = [
            r"(?i)\b(?:debin|d[eé]bito\s+inmediato)\b",
            r"(?i)\b(?:te\s+transfer[ií]\s+(?:por\s+error|de\s+m[aá]s)|transferencia\s+por\s+error)\b",
            r"(?i)\b(?:acept[aá]\s+(?:el\s+debin|la\s+solicitud\s+para\s+devolver))\b",
        ]
        snippets: List[str] = []
        for pat in patterns:
            for match in re.finditer(pat, text):
                snippets.append(match.group(0).strip())
        return len(snippets) > 0, snippets

    def _detect_entity_impersonation(
        self, text: str, context_is_suspicious: bool
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Detección contextual de marcas y entidades.
        Si se mencionan entidades reconocidas pero el contexto contiene
        amenazas, solicitudes de credenciales o premios, se marca como suplantación.
        Si la mención es meramente casual o conversacional sin factores de riesgo, no se alerta.
        """
        entities_dict = {
            "Banco Galicia": r"(?i)\b(?:banco\s+galicia|galicia)\b",
            "Banco Santander": r"(?i)\b(?:banco\s+santander|santander)\b",
            "Banco BBVA": r"(?i)\b(?:banco\s+bbva|bbva|franc[eé]s)\b",
            "Banco Nación": r"(?i)\b(?:banco\s+naci[oó]n|bna)\b",
            "Banco Provincia": r"(?i)\b(?:banco\s+provincia|bapro)\b",
            "Banco Macro": r"(?i)\b(?:banco\s+macro|macro)\b",
            "Mercado Pago": r"(?i)\b(?:mercado\s*pago)\b",
            "Mercado Libre": r"(?i)\b(?:mercado\s*libre)\b",
            "Ualá": r"(?i)\b(?:ual[aá])\b",
            "Cuenta DNI": r"(?i)\b(?:cuenta\s*dni)\b",
            "AFIP / ARCA": r"(?i)\b(?:afip|arca)\b",
            "ANSES": r"(?i)\b(?:anses)\b",
            "Mi Argentina": r"(?i)\b(?:mi\s+argentina)\b",
            "Correo Argentino": r"(?i)\b(?:correo\s+argentino)\b",
            "WhatsApp Oficial": r"(?i)\b(?:soporte\s+de\s+whatsapp|equipo\s+de\s+whatsapp)\b",
        }

        detected_entities: List[str] = []
        snippets: List[str] = []

        for name, regex in entities_dict.items():
            match = re.search(regex, text)
            if match:
                detected_entities.append(name)
                snippets.append(match.group(0).strip())

        # Solo elevar alerta de suplantación si hay contexto sospechoso concomitante
        should_alert = bool(detected_entities and context_is_suspicious)
        return should_alert, snippets, detected_entities
