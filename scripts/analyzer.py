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

    def compose_analysis_from_agent_findings(
        self,
        text: str,
        agent_indicators: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Construye el diccionario `text_analysis` para `RiskClassifier` y `ReportGenerator`
        utilizando los hallazgos validados del `AnalizadorMensajesAgent` para las 5 categorías
        delegadas (urgencia, amenazas, premios, pedidos de datos, pedidos de dinero) sin volver
        a ejecutar esas 5 detecciones ni duplicar reglas.
        Complementa únicamente las 2 verificaciones transversales (`SEC-PROMPT-INJECTION` y
        `SUP-SUPLANTACION-ENTIDAD`) manteniendo el orden canónico y la equivalencia exacta de puntaje.
        """
        if not text:
            return {
                "indicators": [],
                "prompt_injection_detected": False,
                "prompt_injection_details": [],
                "entity_mentions": [],
            }

        # Deduplicar los indicadores recibidos del agente por su id estable
        by_id: Dict[str, Dict[str, Any]] = {}
        for ind in agent_indicators or []:
            ind_id = str(ind.get("id", "")).strip()
            if not ind_id:
                continue
            if ind_id not in by_id:
                by_id[ind_id] = {
                    "id": ind_id,
                    "category": ind.get("category", ""),
                    "severity": ind.get("severity", "ALTA"),
                    "description": ind.get("description", ""),
                    "evidence_snippets": list(ind.get("evidence_snippets") or []),
                }
                if "skill_category" in ind:
                    by_id[ind_id]["skill_category"] = ind["skill_category"]
            else:
                existing_snips = by_id[ind_id]["evidence_snippets"]
                for snip in ind.get("evidence_snippets") or []:
                    if snip not in existing_snips:
                        existing_snips.append(snip)

        indicators: List[Dict[str, Any]] = []

        # 1. Verificación transversal: Prompt Injection
        injection_detected, injection_snippets = self._detect_prompt_injection(text)
        if injection_detected:
            indicators.append({
                "id": "SEC-PROMPT-INJECTION",
                "category": "seguridad_ia",
                "severity": "CRITICA",
                "description": "El mensaje contiene directivas diseñadas para manipular, secuestrar o eludir las instrucciones del agente de IA (Prompt Injection).",
                "evidence_snippets": injection_snippets,
            })

        # 2-7. Insertar los hallazgos del Agente Analizador de Mensajes en el orden canónico
        canonical_agent_order = [
            "ING-AMENAZA-BLOQUEO",
            "ING-URGENCIA-ARTIFICIAL",
            "FRA-CAPTURA-CREDENCIALES",
            "FRA-PREMIO-INESPERADO",
            "FRA-PAGO-ANTICIPADO",
            "FRA-DEBIN-ENGANOSO",
        ]
        for sig_id in canonical_agent_order:
            if sig_id in by_id:
                indicators.append(by_id[sig_id])

        # 8. Verificación transversal: Suplantación contextual usando los hallazgos reales del agente
        context_is_suspicious = any(
            sig_id in by_id
            for sig_id in (
                "ING-AMENAZA-BLOQUEO",
                "FRA-CAPTURA-CREDENCIALES",
                "FRA-PAGO-ANTICIPADO",
                "FRA-PREMIO-INESPERADO",
            )
        )
        entity_detected, entity_snippets, entities = self._detect_entity_impersonation(
            text, context_is_suspicious
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
            r"(?i)\b(?:cuenta(?:\s+bancaria|\s+de\s+correo)?|acceso|tarjeta|servicio|l[ií]nea(?:\s+m[oó]vil)?|buz[oó]n|perfil)\s+(?:ser[aá]\s+|permanecer[aá]\s+)?(?:suspendid[oa]|bloquead[oa]|cancelad[oa]|inhabilitad[oa]|eliminad[oa]|dad[oa]\s+de\s+baja|restringid[oa])\b",
            r"(?i)\b(?:procederemos\s+a\s+|vamos\s+a\s+|se\s+proceder[aá]\s+a\s+)?(?:dar\s+de\s+baja|suspender|bloquear|inhabilitar|cancelar|eliminar)\s+(?:su\s+|tu\s+|la\s+|el\s+)?(?:cuenta(?:\s+de\s+correo)?|servicio|l[ií]nea(?:\s+m[oó]vil)?|buz[oó]n|correo|acceso|suscripci[oó]n)\b",
            r"(?i)\b(?:bloqueo|suspensi[oó]n|inhabilitaci[oó]n|cancelaci[oó]n|baja|eliminaci[oó]n)\s+(?:inmediat[oa]|preventiv[oa]|definitiv[oa]|temporal)\b",
            r"(?i)\b(?:actividad\s+(?:irregular|sospechosa|inusual|an[oó]mala)|acceso\s+no\s+autorizado|inicio\s+de\s+sesi[oó]n\s+(?:sospechoso|irregular)|transferencia\s+saliente\s+no\s+reconocida|denunciado\s+por\s+reiteradas\s+infracciones)\b",
            r"(?i)\b(?:evit(?:ar|e)|para\s+evitar)\s+(?:el\s+bloqueo|la\s+suspensi[oó]n|el\s+cierre|la\s+baja|la\s+cancelaci[oó]n|la\s+eliminaci[oó]n)\b",
            r"(?i)\b(?:cuenta|servicio|acceso|usuario)\s+(?:ser[aá]\s+|permanecer[aá]\s+)?(?:inhabilitad[oa]|suspendid[oa]|bloquead[oa]|restringid[oa])\s*(?:si\s+no|a\s+menos\s+que|hasta\s+que)\b",
            r"(?i)\b(?:el\s+env[ií]o|el\s+paquete)\s+(?:ser[aá]\s+)?(?:devuelto\s+al\s+(?:dep[oó]sito|remitente)|retenido|cancelado)\b",
            r"(?i)\b(?:falta\s+validar\s+(?:el\s+)?domicilio|direcci[oó]n\s+incompleta|problemas?\s+con\s+la\s+entrega)\b",
            r"(?i)\b[uú]ltimo\s+aviso(?:\s+antes\s+de)?\b",
            r"(?i)\b(?:eliminaci[oó]n|cancelaci[oó]n|cierre|desactivaci[oó]n)\s+(?:definitiv[oa]|inmediat[oa])?\s*(?:de\s+(?:su\s+|tu\s+)?(?:cuenta|correo|servicio|buz[oó]n))\b",
            r"(?i)\b(?:dejaremos\s+de\s+(?:procesar|enviar|recibir)|suspenderemos\s+el\s+env[ií]o\s+de|interrupci[oó]n\s+del\s+servicio|superado\s+el\s+\d+%\s+del\s+l[ií]mite|l[ií]mite\s+de\s+almacenamiento)\b",
            r"(?i)\b(?:orden\s+de\s+embargo|embargo\s+preventivo|intimaci[oó]n\s+de\s+pago|aviso\s+de\s+suspensi[oó]n)\b",
        ]
        snippets: List[str] = []
        for pat in patterns:
            for match in re.finditer(pat, text):
                snippets.append(match.group(0).strip())
        return len(snippets) > 0, snippets

    def _detect_urgency(self, text: str) -> Tuple[bool, List[str]]:
        patterns = [
            r"(?i)\b(?:en\s+las\s+pr[oó]ximas\s+(?:\d{1,2}\s+)?(?:horas|hs|minutos|min))\b",
            r"(?i)\b(?:plazo\s+(?:perentorio|improrrogable|l[ií]mite(?:\s+de\s+\d{1,2}\s+(?:horas|hs|d[ií]as))?))\b",
            r"(?i)\b(?:en\s+un\s+plazo\s+de\s+\d{1,2}\s+(?:horas|hs|d[ií]as))\b",
            r"(?i)\b(?:antes\s+de\s+las\s+\d{1,2}(?::\d{2})?\s*(?:hs|horas)?)\b",
            r"(?i)\b(?:de\s+forma\s+urgente|urgente|inmediatamente|a\s+la\s+brevedad|ahora\s+mismo)\b",
            r"(?i)\b(?:quedan\s+\d{1,2}\s+minutos|tiempo\s+l[ií]mite)\b",
            r"(?i)\b(?:(?:bloquead[oa]|suspendid[oa]|vence)\s+hoy|solo\s+por\s+hoy|hoy\s+mismo)\b",
            r"(?i)\b(?:al\s+finalizar\s+(?:la\s+jornada|el\s+d[ií]a)|al\s+cierre\s+(?:de\s+la\s+jornada|del\s+d[ií]a)|antes\s+del\s+cierre\s+(?:de\s+la\s+jornada|del\s+d[ií]a)|al\s+t[eé]rmino\s+del\s+d[ií]a)\b",
            r"(?i)\b(?:vence\s+en\s+(?:\d+|cinco|diez|quince|veinte)\s+minutos|validez\s+de\s+\d+\s+minutos)\b",
            r"(?i)\b[uú]ltima\s+vez\s+que\s+(?:te|le|se)\s+informa\w*\b",
            r"(?i)\b[uú]ltimo\s+aviso\b",
        ]
        snippets: List[str] = []
        for pat in patterns:
            for match in re.finditer(pat, text):
                snippets.append(match.group(0).strip())
        return len(snippets) > 0, snippets

    def _detect_credential_harvesting(self, text: str) -> Tuple[bool, List[str]]:
        patterns = [
            r"(?i)\b(?:token(?:\s+de\s+seguridad)?|clave\s+digital|clave\s+de\s+home\s+banking|clave\s+de\s+cajero|tarjeta\s+de\s+coordenadas|pin(?:\s+de\s+(?:cajero|autogesti[oó]n|seguridad))?)\b",
            r"(?i)\b(?:c[oó]digo\s+(?:de\s+seguridad|de\s+verificaci[oó]n|sms|otp|(?:de\s+)?(?:\d+|cuatro|seis|ocho)\s+d[ií]gitos))\b",
            r"(?i)\b(?:c[oó]digo(?:\s+que)?\s+(?:te|le)\s+(?:acaba\s+de\s+llegar|lleg[oó]|enviamos)\s*(?:por\s+sms|por\s+mensaje)?)\b",
            r"(?i)\b(?:reingresar|reingres[ae]|reingresando|ingresar|ingres[ae]|ingresando|confirmar|confirm[ae]|confirmando|validar|valid[ae]|validando|actualizar|actualic[ee]|actualizando|solicitar|solicit[ae]|solicitando|compartir|compart[ae]s?|compartiendo|pas[ae]s?|enviar|env[ií][ae]s?|enviando|pedir|pid[ae])\s+(?:el\s+|la\s+|su\s+|tu\s+|un\s+)?(?:usuario|clave|documento|contrase[ñn]a|token|pin|c[oó]digo|dni|cbu|cvu)\b",
            r"(?i)\b(?:confirmar|confirm[aáeé]|confirmando|validar|valid[aáeé]|validando|actualizar|actualic[ee]|actualizando)\s+(?:sus?\s+|tus?\s+)?(?:datos(?:\s+personales)?|identidad|domicilio|titularidad)\b",
            r"(?i)\b(?:enlace\s+para\s+verificar\s+(?:su\s+)?identidad|formulario\s+oficial\s+para\s+(?:verificar|apelar)|cancelar\s+(?:la\s+operaci[oó]n|la\s+transacci[oó]n|el\s+retiro))\b",
            r"(?i)\b(?:complet[aáeé]|completando|realiz[aáeé]|realizando|hac[eé]|haga|inici[aáeé])\s+(?:la\s+|el\s+|una\s+|su\s+|tu\s+|nuestra\s+)?verificaci[oó]n(?:\s+de\s+(?:seguridad|identidad|datos|cuenta|titularidad))?\b",
            r"(?i)\b(?:verificar|validar|actualizar)\s+(?:la\s+actualizaci[oó]n|su\s+cuenta|tu\s+cuenta|sus\s+datos|tus\s+datos|sus?\s+credenciales|m[eé]todo\s+de\s+pago|tarjeta\s+de\s+cr[eé]dito|buz[oó]n)\b",
            r"(?i)\b(?:centro\s+de\s+(?:verificaci[oó]n|seguridad|actualizaci[oó]n)|complete\s+el\s+procedimiento(?:\s+solicitado)?)\b",
            r"(?i)\b(?:verificaci[oó]n\s+de\s+seguridad\s+obligatoria|portal\s+de\s+seguridad)\b",
        ]
        snippets: List[str] = []
        for pat in patterns:
            for match in re.finditer(pat, text):
                # Salvaguarda de contexto educativo o preventivo legítimo (evita falsos positivos)
                window_start = max(0, match.start() - 120)
                window = text[window_start:match.end()]
                if re.search(r"(?i)\b(?:nunca|jam[aá]s|en\s+ning[uú]n\s+caso)\s+(?:te\s+|le\s+|se\s+)?(?:pedir\w*|solicitar\w*|llamar\w*|enviar\w*|compartas|entregues|brindes)", window):
                    continue
                if re.search(r"(?i)\b(?:no\s+(?:compartas|reveles|entregues|env[ií]es|des|brindes))\b", window):
                    continue
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
            r"(?i)\b(?:abonar|pagar|transferir|abon[aáeé]|pag[aáeé]|transfer[ií])\s+(?:el\s+|la\s+|los\s+)?(?:costo\s+de\s+(?:gesti[oó]n|env[ií]o|entrega|reprogramaci[oó]n)|tasa|seguro\s+postal|estampillado|gastos\s+administrativos|arancel|flete)\b",
            r"(?i)\b(?:para\s+(?:reprogramar|coordinar|confirmar)\s+la\s+entrega|para\s+liberar\s+el\s+(?:premio|paquete|env[ií]o))\b",
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
            "Soporte Técnico": r"(?i)\b(?:soy\s+del\s+soporte(?:\s+t[eé]cnico)?|equipo\s+de\s+soporte(?:\s+t[eé]cnico)?|servicio\s+t[eé]cnico|mesa\s+de\s+ayuda)\b",
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
