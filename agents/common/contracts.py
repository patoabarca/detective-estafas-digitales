"""
Contratos de Datos y Validadores Estructurados para Agentes y Herramientas.

Define y valida los formatos de entrada, llamadas a herramientas, resultados del
Agente Preparador, resultados del Agente Analizador de Mensajes, resultados del
Agente Analizador de Enlaces y respuestas del Agente Orquestador.

Cumple con los requerimientos de las Etapas 1, 2 y 3:
- El preparador devuelve `PreparationResult`:
  - estado: "correcto" | "incompleto" | "error"
  - texto_extraido_o_recibido: str
  - enlaces_encontrados: List[str]
  - advertencias: List[str]
  - detalle_estado: "con_enlaces" | "sin_enlaces" | "texto_no_extraible" | "entrada_invalida" | "fallo_herramienta"
- El analizador de mensajes devuelve `MessageAnalysisResult`:
  - estado: "correcto" | "incompleto" | "error"
  - categorias_revisadas: List[str]
  - estado_categorias: Dict[str, str] diferenciando "revisada_con_hallazgos", "revisada_sin_hallazgos" y "no_revisada"
  - senales_encontradas: List[MessageSignalFinding] (con id estable, categoría, fragmento verificado contra el texto analizado)
  - advertencias: List[str]
- El analizador de enlaces devuelve `UrlAnalysisResult`:
  - estado: "correcto" | "incompleto" | "error"
  - detalle_estado: "sin_enlaces" | "analizados_sin_senales" | "analizados_con_senales" | "direccion_no_analizable" | "enlaces_omitidos" | "fallo_herramienta"
  - intervino_agente: bool
  - cantidad_enlaces_extraidos: int
  - cantidad_enlaces_procesados: int
  - enlaces_analizados: List[UrlItemAnalysisResult]
  - advertencias: List[str]
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional


VALID_PREPARATION_STATES = {"correcto", "incompleto", "error"}
VALID_DETAIL_CODES = {
    "con_enlaces",
    "sin_enlaces",
    "texto_no_extraible",
    "entrada_invalida",
    "fallo_herramienta",
}
VALID_INPUT_MODES = {"text", "ocr_screenshot"}

REQUIRED_MESSAGE_ANALYSIS_CATEGORIES: List[str] = [
    "urgencia",
    "amenazas",
    "premios",
    "pedidos_datos",
    "pedidos_dinero",
]
VALID_MESSAGE_ANALYSIS_CATEGORIES = set(REQUIRED_MESSAGE_ANALYSIS_CATEGORIES)
VALID_MESSAGE_SIGNAL_IDS = {
    "ING-URGENCIA-ARTIFICIAL",
    "ING-AMENAZA-BLOQUEO",
    "FRA-PREMIO-INESPERADO",
    "FRA-CAPTURA-CREDENCIALES",
    "FRA-PAGO-ANTICIPADO",
    "FRA-DEBIN-ENGANOSO",
}
VALID_CATEGORY_STATUSES = {
    "revisada_con_hallazgos",
    "revisada_sin_hallazgos",
    "no_revisada",
}

VALID_URL_RULE_IDS = {
    "REGLA-URL-01",
    "REGLA-URL-02",
    "REGLA-URL-03",
    "REGLA-URL-04",
    "REGLA-URL-05",
    "INFO-URL-HTTP",
    "INFO-URL-HTTPS",
    "INFO-URL-SENSITIVE-PARAMS",
}
VALID_URL_ITEM_STATUSES = {
    "analizado_con_senales",
    "analizado_sin_senales",
    "direccion_no_analizable",
    "no_procesado",
    "error_herramienta",
}
VALID_URL_ANALYSIS_DETAIL_CODES = {
    "sin_enlaces",
    "analizados_sin_senales",
    "analizados_con_senales",
    "direccion_no_analizable",
    "enlaces_omitidos",
    "fallo_herramienta",
}


class ContractValidationError(ValueError):
    """Error lanzado cuando una entrada, argumento de herramienta o respuesta viola el contrato."""
    pass


@dataclass
class AgentInputRequest:
    """Contrato de entrada hacia el sistema de agentes."""
    input_mode: Literal["text", "ocr_screenshot"]
    text_content: str = ""
    image_bytes: Optional[bytes] = None
    image_filename: str = ""

    def validate_envelope(self) -> None:
        if self.input_mode not in VALID_INPUT_MODES:
            raise ContractValidationError(
                f"Modalidad de entrada no permitida: '{self.input_mode}'. "
                f"Valores válidos: {sorted(VALID_INPUT_MODES)}"
            )
        if not isinstance(self.text_content, str):
            raise ContractValidationError("El campo 'text_content' debe ser una cadena (str).")
        if self.image_bytes is not None and not isinstance(self.image_bytes, bytes):
            raise ContractValidationError("El campo 'image_bytes' debe ser bytes o None.")


@dataclass
class ToolCallRecord:
    """Registro validado de una invocación a herramienta por parte de un agente."""
    agent_name: str
    tool_name: str
    arguments: Dict[str, Any]
    status: Literal["ok", "error", "rejected"]
    summary: str
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PreparationResult:
    """
    Contrato estricto de salida del Agente Preparador.

    Diferencia explícitamente:
    - estado == "correcto" con detalle_estado == "con_enlaces" o "sin_enlaces"
    - estado == "incompleto" con detalle_estado == "texto_no_extraible" (captura ilegible/vacía)
    - estado == "error" con detalle_estado == "entrada_invalida" o "fallo_herramienta"
    """
    estado: Literal["correcto", "incompleto", "error"]
    detalle_estado: Literal[
        "con_enlaces",
        "sin_enlaces",
        "texto_no_extraible",
        "entrada_invalida",
        "fallo_herramienta",
    ]
    texto_extraido_o_recibido: str = ""
    enlaces_encontrados: List[str] = field(default_factory=list)
    advertencias: List[str] = field(default_factory=list)
    mensaje_error: Optional[str] = None
    modalidad_entrada: str = "text"
    url_details: List[Dict[str, Any]] = field(default_factory=list)
    ocr_url_warnings: List[Dict[str, str]] = field(default_factory=list)
    skills_cargadas: List[str] = field(default_factory=list)
    herramientas_invocadas: List[str] = field(default_factory=list)

    def validate(self) -> None:
        if self.estado not in VALID_PREPARATION_STATES:
            raise ContractValidationError(
                f"Estado de preparación inválido: '{self.estado}'. "
                f"Permitidos: {sorted(VALID_PREPARATION_STATES)}"
            )
        if self.detalle_estado not in VALID_DETAIL_CODES:
            raise ContractValidationError(
                f"Detalle de estado inválido: '{self.detalle_estado}'. "
                f"Permitidos: {sorted(VALID_DETAIL_CODES)}"
            )
        if not isinstance(self.texto_extraido_o_recibido, str):
            raise ContractValidationError("'texto_extraido_o_recibido' debe ser str.")
        if not isinstance(self.enlaces_encontrados, list) or not all(
            isinstance(u, str) for u in self.enlaces_encontrados
        ):
            raise ContractValidationError("'enlaces_encontrados' debe ser una lista de cadenas (List[str]).")
        if not isinstance(self.advertencias, list) or not all(
            isinstance(w, str) for w in self.advertencias
        ):
            raise ContractValidationError("'advertencias' debe ser una lista de cadenas (List[str]).")

        # Reglas de coherencia semántica:
        # Una captura ilegible o sin texto NUNCA puede tener estado "correcto"
        if self.estado == "correcto" and not self.texto_extraido_o_recibido.strip():
            raise ContractValidationError(
                "Inconsistencia de contrato: el estado no puede ser 'correcto' si el texto está vacío."
            )
        if self.detalle_estado == "texto_no_extraible" and self.estado != "incompleto":
            raise ContractValidationError(
                "Cuando no se pudo extraer texto ('texto_no_extraible'), el estado debe ser 'incompleto'."
            )
        if self.detalle_estado in ("entrada_invalida", "fallo_herramienta") and self.estado != "error":
            raise ContractValidationError(
                f"El detalle '{self.detalle_estado}' requiere obligatoriamente estado='error'."
            )

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PreparationResult":
        if not isinstance(data, dict):
            raise ContractValidationError("Se esperaba un diccionario para construir PreparationResult.")
        obj = cls(
            estado=data.get("estado", "error"),
            detalle_estado=data.get("detalle_estado", "fallo_herramienta"),
            texto_extraido_o_recibido=str(data.get("texto_extraido_o_recibido", "") or ""),
            enlaces_encontrados=list(data.get("enlaces_encontrados") or []),
            advertencias=[str(w) for w in (data.get("advertencias") or [])],
            mensaje_error=data.get("mensaje_error"),
            modalidad_entrada=str(data.get("modalidad_entrada", "text")),
            url_details=list(data.get("url_details") or []),
            ocr_url_warnings=list(data.get("ocr_url_warnings") or []),
            skills_cargadas=list(data.get("skills_cargadas") or []),
            herramientas_invocadas=list(data.get("herramientas_invocadas") or []),
        )
        obj.validate()
        return obj


@dataclass
class MessageSignalFinding:
    """
    Contrato validado para una señal detectada por el Agente Analizador de Mensajes.
    Cada señal debe tener un identificador estable, categoría y al menos un fragmento
    que exista literalmente en el texto analizado.
    """
    id_senal: str
    categoria_skill: str
    categoria_motor: str
    severidad: str
    descripcion: str
    fragmento_justificacion: str
    evidence_snippets: List[str] = field(default_factory=list)

    def validate(self, analyzed_text: Optional[str] = None) -> None:
        if self.id_senal not in VALID_MESSAGE_SIGNAL_IDS:
            raise ContractValidationError(
                f"Identificador de señal inválido: '{self.id_senal}'. "
                f"Permitidos: {sorted(VALID_MESSAGE_SIGNAL_IDS)}"
            )
        if self.categoria_skill not in VALID_MESSAGE_ANALYSIS_CATEGORIES:
            raise ContractValidationError(
                f"Categoría de skill inválida: '{self.categoria_skill}'. "
                f"Permitidas: {sorted(VALID_MESSAGE_ANALYSIS_CATEGORIES)}"
            )
        if not isinstance(self.fragmento_justificacion, str) or not self.fragmento_justificacion.strip():
            raise ContractValidationError(
                f"La señal '{self.id_senal}' carece de fragmento de justificación válido."
            )
        if not isinstance(self.evidence_snippets, list) or not self.evidence_snippets:
            raise ContractValidationError(
                f"La señal '{self.id_senal}' debe incluir al menos un fragmento en 'evidence_snippets'."
            )

        # Verificación estricta anti-alucinación en código:
        # todo fragmento debe corresponder literalmente al texto analizado.
        if analyzed_text is not None:
            if self.fragmento_justificacion not in analyzed_text:
                raise ContractValidationError(
                    f"Evidencia inventada rechazada en '{self.id_senal}': el fragmento "
                    f"'{self.fragmento_justificacion[:80]}' no existe en el texto analizado."
                )
            for snip in self.evidence_snippets:
                if not isinstance(snip, str) or not snip.strip() or snip not in analyzed_text:
                    raise ContractValidationError(
                        f"Evidencia inventada rechazada en '{self.id_senal}': el snippet "
                        f"'{str(snip)[:80]}' no pertenece al texto analizado."
                    )

    def to_engine_indicator(self) -> Dict[str, Any]:
        """Convierte el hallazgo validado al formato exacto esperado por RiskClassifier y ReportGenerator."""
        return {
            "id": self.id_senal,
            "category": self.categoria_motor,
            "skill_category": self.categoria_skill,
            "severity": self.severidad,
            "description": self.descripcion,
            "evidence_snippets": list(self.evidence_snippets),
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MessageAnalysisResult:
    """
    Contrato estricto de salida del Agente Analizador de Mensajes (Etapa 2).

    Garantiza:
    - Estado: "correcto" | "incompleto" | "error".
    - Diferenciación explícita entre "revisada_con_hallazgos", "revisada_sin_hallazgos" y "no_revisada".
    - Prohibición de marcar estado == "correcto" si falta cualquiera de las 5 categorías obligatorias.
    - Verificación de evidencia literal contra el texto analizado.
    """
    estado: Literal["correcto", "incompleto", "error"]
    categorias_revisadas: List[str] = field(default_factory=list)
    categorias_sin_hallazgos: List[str] = field(default_factory=list)
    categorias_no_revisadas: List[str] = field(default_factory=list)
    estado_categorias: Dict[str, str] = field(default_factory=dict)
    senales_encontradas: List[MessageSignalFinding] = field(default_factory=list)
    advertencias: List[str] = field(default_factory=list)
    mensaje_error: Optional[str] = None
    skills_cargadas: List[str] = field(default_factory=list)
    herramientas_invocadas: List[str] = field(default_factory=list)

    def validate(self, analyzed_text: Optional[str] = None) -> None:
        if self.estado not in VALID_PREPARATION_STATES:
            raise ContractValidationError(
                f"Estado de análisis de mensaje inválido: '{self.estado}'."
            )
        if not isinstance(self.categorias_revisadas, list):
            raise ContractValidationError("'categorias_revisadas' debe ser una lista.")
        for c in self.categorias_revisadas:
            if c not in VALID_MESSAGE_ANALYSIS_CATEGORIES:
                raise ContractValidationError(f"Categoría desconocida en 'categorias_revisadas': '{c}'.")

        for cat_key, cat_status in self.estado_categorias.items():
            if cat_key not in VALID_MESSAGE_ANALYSIS_CATEGORIES:
                raise ContractValidationError(f"Categoría desconocida en 'estado_categorias': '{cat_key}'.")
            if cat_status not in VALID_CATEGORY_STATUSES:
                raise ContractValidationError(
                    f"Estado de categoría inválido para '{cat_key}': '{cat_status}'."
                )

        # No marcar el análisis como completo ("correcto") si faltan categorías obligatorias
        missing_required = set(REQUIRED_MESSAGE_ANALYSIS_CATEGORIES) - set(self.categorias_revisadas)
        if self.estado == "correcto" and missing_required:
            raise ContractValidationError(
                f"Inconsistencia de contrato: el análisis de mensaje no puede tener estado='correcto' "
                f"cuando faltan categorías obligatorias sin revisar: {sorted(missing_required)}."
            )

        for sig in self.senales_encontradas:
            if not isinstance(sig, MessageSignalFinding):
                raise ContractValidationError("Todos los elementos de 'senales_encontradas' deben ser MessageSignalFinding.")
            sig.validate(analyzed_text=analyzed_text)
            if sig.categoria_skill not in self.categorias_revisadas:
                raise ContractValidationError(
                    f"La señal '{sig.id_senal}' pertenece a una categoría ('{sig.categoria_skill}') "
                    f"que no figura como revisada."
                )

    def to_engine_indicators(self) -> List[Dict[str, Any]]:
        """Devuelve la lista deduplicada de indicadores para `RiskClassifier`."""
        seen_ids: Dict[str, Dict[str, Any]] = {}
        for sig in self.senales_encontradas:
            ind = sig.to_engine_indicator()
            sig_id = ind["id"]
            if sig_id not in seen_ids:
                seen_ids[sig_id] = ind
            else:
                existing_snips = seen_ids[sig_id]["evidence_snippets"]
                for snip in ind["evidence_snippets"]:
                    if snip not in existing_snips:
                        existing_snips.append(snip)
        return list(seen_ids.values())

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        data = asdict(self)
        data["senales_encontradas"] = [s.to_dict() for s in self.senales_encontradas]
        return data


@dataclass
class UrlSignalFinding:
    """
    Contrato validado para una señal detectada sobre una URL por el Agente Analizador de Enlaces.
    """
    id_regla: str
    tipo_senal: str
    evidencia: str
    descripcion: str

    def validate(self, raw_url: Optional[str] = None, domain: Optional[str] = None) -> None:
        if self.id_regla not in VALID_URL_RULE_IDS:
            raise ContractValidationError(
                f"Identificador de regla URL inválido: '{self.id_regla}'. "
                f"Permitidos: {sorted(VALID_URL_RULE_IDS)}"
            )
        if not isinstance(self.evidencia, str) or not self.evidencia.strip():
            raise ContractValidationError(
                f"La señal '{self.id_regla}' debe incluir evidencia concreta no vacía."
            )
        if not isinstance(self.descripcion, str) or not self.descripcion.strip():
            raise ContractValidationError(
                f"La señal '{self.id_regla}' debe incluir descripción no vacía."
            )
        if raw_url is not None and self.evidencia not in raw_url and (not domain or self.evidencia not in domain):
            raise ContractValidationError(
                f"Evidencia de URL inválida en '{self.id_regla}': '{self.evidencia}' no corresponde a '{raw_url}'."
            )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UrlItemAnalysisResult:
    """
    Resultado estructurado del análisis estático de un enlace individual.
    Conserva los campos exactos requeridos por `RiskClassifier` y `ReportGenerator`
    (`raw_url`, `scheme`, `domain`, `port`, `is_ip_address`, `has_punycode`, `has_userinfo`, `findings`).
    """
    url_id: str
    raw_url: str
    masked_url: str
    estado_enlace: Literal[
        "analizado_con_senales",
        "analizado_sin_senales",
        "direccion_no_analizable",
        "no_procesado",
        "error_herramienta",
    ]
    scheme: str = "desconocido"
    domain: str = "no_identificado"
    port: Optional[int] = None
    is_ip_address: bool = False
    has_punycode: bool = False
    has_userinfo: bool = False
    findings: List[str] = field(default_factory=list)
    senales_encontradas: List[UrlSignalFinding] = field(default_factory=list)
    reglas_activadas: List[str] = field(default_factory=list)
    advertencias: List[str] = field(default_factory=list)
    ocr_warnings: List[Dict[str, str]] = field(default_factory=list)

    def validate(self, allowed_raw_urls: Optional[List[str]] = None) -> None:
        if not isinstance(self.url_id, str) or not self.url_id.strip():
            raise ContractValidationError("Cada enlace debe tener un identificador 'url_id' válido.")
        if not isinstance(self.raw_url, str) or not self.raw_url.strip():
            raise ContractValidationError(f"El enlace '{self.url_id}' carece de 'raw_url'.")
        if self.estado_enlace not in VALID_URL_ITEM_STATUSES:
            raise ContractValidationError(
                f"Estado de enlace inválido en '{self.url_id}': '{self.estado_enlace}'."
            )
        if allowed_raw_urls is not None and self.raw_url not in allowed_raw_urls:
            raise ContractValidationError(
                f"URL inventada o sustituida rechazada en '{self.url_id}': '{self.raw_url}' "
                f"no pertenece a las direcciones extraídas de la sesión."
            )
        for sig in self.senales_encontradas:
            if not isinstance(sig, UrlSignalFinding):
                raise ContractValidationError("Los elementos de 'senales_encontradas' deben ser UrlSignalFinding.")
            sig.validate(raw_url=self.raw_url, domain=self.domain)

    def to_engine_url_dict(self) -> Dict[str, Any]:
        """Devuelve el diccionario exacto que esperan `RiskClassifier` y `ReportGenerator`."""
        return {
            "url_id": self.url_id,
            "raw_url": self.raw_url,
            "scheme": self.scheme,
            "domain": self.domain,
            "port": self.port,
            "is_ip_address": self.is_ip_address,
            "has_punycode": self.has_punycode,
            "has_userinfo": self.has_userinfo,
            "findings": list(self.findings),
            "rule_ids": list(self.reglas_activadas),
            "status": self.estado_enlace,
            "ocr_warnings": list(self.ocr_warnings),
        }

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        data = asdict(self)
        data["senales_encontradas"] = [s.to_dict() for s in self.senales_encontradas]
        return data


@dataclass
class UrlAnalysisResult:
    """
    Contrato estricto de salida del Agente Analizador de Enlaces (Etapa 3).

    Garantiza:
    - Estado: "correcto" | "incompleto" | "error".
    - Diferenciación explícita entre:
      * "sin_enlaces": no había enlaces en el mensaje (se omite el agente sin error).
      * "analizados_sin_senales": se analizaron todos los enlaces y no se hallaron señales de riesgo
        (con advertencia explícita de que esto NO garantiza legitimidad).
      * "analizados_con_senales": se analizaron todos los enlaces y se detectaron señales.
      * "direccion_no_analizable": alguna dirección estaba malformada o sin host identificable (`estado="incompleto"`).
      * "enlaces_omitidos": no se procesaron todos los enlaces extraídos (`estado="incompleto"`).
      * "fallo_herramienta": ocurrió un error técnico (`estado="error"`).
    - Prohibición de marcar `estado == "correcto"` si se omitieron enlaces extraídos o si alguna URL no pudo analizarse.
    """
    estado: Literal["correcto", "incompleto", "error"]
    detalle_estado: Literal[
        "sin_enlaces",
        "analizados_sin_senales",
        "analizados_con_senales",
        "direccion_no_analizable",
        "enlaces_omitidos",
        "fallo_herramienta",
    ]
    intervino_agente: bool = True
    motivo_omision: Optional[str] = None
    cantidad_enlaces_extraidos: int = 0
    cantidad_enlaces_procesados: int = 0
    enlaces_analizados: List[UrlItemAnalysisResult] = field(default_factory=list)
    enlaces_omitidos: List[str] = field(default_factory=list)
    advertencias: List[str] = field(default_factory=list)
    mensaje_error: Optional[str] = None
    skills_cargadas: List[str] = field(default_factory=list)
    herramientas_invocadas: List[str] = field(default_factory=list)

    def validate(self, expected_urls: Optional[List[str]] = None) -> None:
        if self.estado not in VALID_PREPARATION_STATES:
            raise ContractValidationError(
                f"Estado de análisis de enlaces inválido: '{self.estado}'."
            )
        if self.detalle_estado not in VALID_URL_ANALYSIS_DETAIL_CODES:
            raise ContractValidationError(
                f"Detalle de estado de análisis de enlaces inválido: '{self.detalle_estado}'."
            )
        if self.cantidad_enlaces_extraidos < 0 or self.cantidad_enlaces_procesados < 0:
            raise ContractValidationError("Las cantidades de enlaces no pueden ser negativas.")

        # Prohibido declarar completo ("correcto") un análisis que omitió enlaces
        if self.estado == "correcto":
            if self.enlaces_omitidos:
                raise ContractValidationError(
                    "Inconsistencia de contrato: el análisis de enlaces no puede tener estado='correcto' "
                    f"cuando existen enlaces omitidos: {self.enlaces_omitidos}."
                )
            if self.cantidad_enlaces_procesados < self.cantidad_enlaces_extraidos:
                raise ContractValidationError(
                    "Inconsistencia de contrato: el análisis de enlaces no puede ser 'correcto' si "
                    f"se procesaron {self.cantidad_enlaces_procesados} de {self.cantidad_enlaces_extraidos} enlaces."
                )
            if any(
                item.estado_enlace in ("direccion_no_analizable", "no_procesado", "error_herramienta")
                for item in self.enlaces_analizados
            ):
                raise ContractValidationError(
                    "Inconsistencia de contrato: un enlace con estado 'direccion_no_analizable', 'no_procesado' "
                    "o 'error_herramienta' impide que el resultado global sea 'correcto'."
                )

        if self.detalle_estado in ("direccion_no_analizable", "enlaces_omitidos") and self.estado != "incompleto":
            raise ContractValidationError(
                f"Cuando detalle_estado es '{self.detalle_estado}', el estado debe ser 'incompleto'."
            )
        if self.detalle_estado == "fallo_herramienta" and self.estado != "error":
            raise ContractValidationError(
                "Cuando detalle_estado es 'fallo_herramienta', el estado debe ser 'error'."
            )

        for item in self.enlaces_analizados:
            if not isinstance(item, UrlItemAnalysisResult):
                raise ContractValidationError(
                    "Todos los elementos de 'enlaces_analizados' deben ser UrlItemAnalysisResult."
                )
            item.validate(allowed_raw_urls=expected_urls)

        if expected_urls is not None and self.estado == "correcto" and self.cantidad_enlaces_extraidos > 0:
            analyzed_raw = [it.raw_url for it in self.enlaces_analizados]
            if analyzed_raw != list(expected_urls):
                raise ContractValidationError(
                    "Inconsistencia de contrato: la lista de enlaces analizados no coincide con los enlaces "
                    "extraídos de la sesión."
                )

    def to_engine_url_analyses(self) -> List[Dict[str, Any]]:
        """Devuelve la lista de diccionarios para `RiskClassifier` y `ReportGenerator` sin re-ejecutar `url_analyzer`."""
        return [item.to_engine_url_dict() for item in self.enlaces_analizados]

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        data = asdict(self)
        data["enlaces_analizados"] = [it.to_dict() for it in self.enlaces_analizados]
        return data


VALID_EVALUATION_STATES = {"correcto", "incompleto", "error"}
VALID_RISK_LEVELS = {"ALTO", "MEDIO", "BAJO", "INDETERMINADO"}


@dataclass
class EvaluationResult:
    """
    Contrato inmutable y validado del resultado emitido por el Agente Evaluador (Etapa 4).
    """
    estado: Literal["correcto", "incompleto", "error"]
    detalle_estado: str
    nivel_riesgo: str = "INDETERMINADO"
    puntaje: int = 0
    resumen: str = ""
    explicacion_no_tecnica: str = ""
    reglas_activadas: List[str] = field(default_factory=list)
    recomendaciones: List[str] = field(default_factory=list)
    limitaciones: List[str] = field(default_factory=list)
    hallazgos_unificados: List[Dict[str, Any]] = field(default_factory=list)
    analisis_urls: List[Dict[str, Any]] = field(default_factory=list)
    advertencias: List[str] = field(default_factory=list)
    pdf_generado: bool = False
    pdf_filename: Optional[str] = None
    mensaje_error: Optional[str] = None
    skills_cargadas: List[str] = field(default_factory=list)
    herramientas_invocadas: List[str] = field(default_factory=list)

    def validate(self) -> None:
        if self.estado not in VALID_EVALUATION_STATES:
            raise ContractValidationError(
                f"Estado de evaluación inválido: '{self.estado}'. Valores permitidos: {VALID_EVALUATION_STATES}."
            )
        if self.nivel_riesgo not in VALID_RISK_LEVELS:
            raise ContractValidationError(
                f"Nivel de riesgo inválido: '{self.nivel_riesgo}'. Valores permitidos: {VALID_RISK_LEVELS}."
            )
        if not (0 <= self.puntaje <= 100):
            raise ContractValidationError(
                f"Puntaje de evaluación fuera de rango: {self.puntaje}. Debe estar entre 0 y 100."
            )
        # Garantía estricta de seguridad: si la evaluación es incompleta o con error,
        # NUNCA puede declararse como RIESGO BAJO.
        if self.estado in ("incompleto", "error") and self.nivel_riesgo == "BAJO":
            raise ContractValidationError(
                "Violación de seguridad: una evaluación incompleta o con error no puede clasificarse como RIESGO BAJO."
            )

    def to_engine_report(self) -> Dict[str, Any]:
        """Convierte la evaluación al esquema unificado del reporte JSON de la aplicación."""
        from datetime import datetime, timezone
        injection_snips = [
            snip
            for ind in self.hallazgos_unificados
            if ind.get("id") == "SEC-PROMPT-INJECTION"
            for snip in ind.get("evidence_snippets", [])
        ]
        return {
            "status": "success" if self.estado == "correcto" else self.estado,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "risk_assessment": {
                "level": self.nivel_riesgo,
                "score": self.puntaje,
                "score_type": "heuristic_severity_score",
                "score_disclaimer": "Puntaje heurístico acumulativo (0-100). No representa una probabilidad estadística de fraude.",
                "summary": self.resumen,
                "activated_rules": list(self.reglas_activadas),
            },
            "indicators_detected": list(self.hallazgos_unificados),
            "url_analysis": list(self.analisis_urls),
            "prompt_injection_detected": any(
                ind.get("id") == "SEC-PROMPT-INJECTION" for ind in self.hallazgos_unificados
            ),
            "prompt_injection_details": injection_snips,
            "limitations": list(self.limitaciones),
            "recommendations": list(self.recomendaciones),
            "non_technical_explanation": self.explicacion_no_tecnica,
        }

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass
class OrchestratorResponse:
    """
    Contrato de salida del Agente Orquestador hacia la aplicación Streamlit.
    """
    status: Literal["success", "incomplete", "error"]
    execution_mode: Literal["agent_orchestrated"] = "agent_orchestrated"
    provider: str = "google-genai"
    model_used: str = ""
    preparation: Optional[PreparationResult] = None
    message_analysis: Optional[MessageAnalysisResult] = None
    url_analysis: Optional[UrlAnalysisResult] = None
    evaluation: Optional[EvaluationResult] = None
    report: Optional[Dict[str, Any]] = None
    orchestrator_summary: str = ""
    privacy_notice: Dict[str, Any] = field(default_factory=dict)
    usage_metrics: Dict[str, Any] = field(default_factory=dict)
    trace_events: List[Dict[str, Any]] = field(default_factory=list)
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    def validate(self) -> None:
        if self.status not in ("success", "incomplete", "error"):
            raise ContractValidationError(f"Estado de orquestador inválido: '{self.status}'")
        if self.preparation is not None:
            self.preparation.validate()
        if self.message_analysis is not None:
            ref_text = (
                self.preparation.texto_extraido_o_recibido
                if self.preparation and self.preparation.texto_extraido_o_recibido
                else None
            )
            self.message_analysis.validate(analyzed_text=ref_text)
        if self.url_analysis is not None:
            expected_urls = (
                self.preparation.enlaces_encontrados
                if self.preparation is not None
                else None
            )
            self.url_analysis.validate(expected_urls=expected_urls)
        if self.evaluation is not None:
            self.evaluation.validate()
        # Garantía de seguridad: si la preparación o algún análisis quedó incompleto,
        # el reporte NUNCA puede clasificar como RIESGO BAJO.
        if self.report and isinstance(self.report, dict):
            risk_level = self.report.get("risk_assessment", {}).get("level")
            if self.status == "incomplete" and risk_level == "BAJO":
                raise ContractValidationError(
                    "Violación de seguridad: una entrada o análisis incompleto no puede evaluarse como RIESGO BAJO."
                )

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        result = asdict(self)
        if self.preparation is not None:
            result["preparation"] = self.preparation.to_dict()
        if self.message_analysis is not None:
            result["message_analysis"] = self.message_analysis.to_dict()
        if self.url_analysis is not None:
            result["url_analysis"] = self.url_analysis.to_dict()
        if self.evaluation is not None:
            result["evaluation"] = self.evaluation.to_dict()
        return result


def validate_tool_arguments(
    tool_name: str,
    args: Any,
    allowed_params: Dict[str, Any],
    required_params: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Valida estrictamente los argumentos suministrados por el modelo a una herramienta:
    - Debe ser un diccionario.
    - No se permiten claves fuera de `allowed_params` (lista cerrada de parámetros).
    - Todos los `required_params` deben estar presentes.
    - Los tipos deben coincidir con `allowed_params`.
    """
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ContractValidationError(
            f"Argumentos inválidos para '{tool_name}': se esperaba un objeto JSON/dict."
        )

    unknown_keys = set(args.keys()) - set(allowed_params.keys())
    if unknown_keys:
        raise ContractValidationError(
            f"Argumentos no permitidos en '{tool_name}': {sorted(unknown_keys)}. "
            f"Parámetros aceptados: {sorted(allowed_params.keys())}"
        )

    for req in (required_params or []):
        if req not in args or args[req] is None:
            raise ContractValidationError(
                f"Falta el argumento obligatorio '{req}' en la llamada a '{tool_name}'."
            )

    validated: Dict[str, Any] = {}
    for k, v in args.items():
        expected_type = allowed_params[k]
        # En Python bool es subclase de int; evitar que un bool pase como int si se pide int
        if expected_type is int and isinstance(v, bool):
            raise ContractValidationError(
                f"Tipo inválido para '{k}' en '{tool_name}': se esperaba int, se recibió bool."
            )
        if not isinstance(v, expected_type):
            type_name = getattr(expected_type, "__name__", str(expected_type))
            raise ContractValidationError(
                f"Tipo inválido para '{k}' en '{tool_name}': se esperaba {type_name}, "
                f"se recibió {type(v).__name__}."
            )
        validated[k] = v

    return validated
