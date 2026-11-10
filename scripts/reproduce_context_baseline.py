"""
Script de Medición y Línea Base Reproducible del Contexto Efectivamente Enviado al Modelo.

Ejecuta tres escenarios determinísticos con clientes simulados y datos 100% ficticios:
1. Texto sin enlaces.
2. Texto con dos enlaces ficticios.
3. Captura con OCR simulado y enlace.

Mide por agente y por turno:
- Instrucción de sistema (system_instruction).
- Declaraciones de herramientas (tool_declarations).
- Contenido e historial enviados (contents).
- Respuestas de herramientas incluidas en ese historial (tool_responses_breakdown, como desglose).
- Total de solicitud por turno y total acumulado por escenario.

Aclaración obligatoria:
Estos resultados describen los recorridos programados del cliente simulado; no demuestran
cuántos turnos ni tokens usará Gemini real.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Asegurar raíz del proyecto en sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image

from agents.common.context_metrics import (
    ContextRecordingClientWrapper,
    ContextRecordingCollector,
)
from agents.common.contracts import AgentInputRequest
from agents.orquestador.agent import OrquestadorAgent

from tests.test_agents_orchestration import (
    make_standard_analizador_enlaces_mock_client,
    make_standard_analizador_mensajes_mock_client,
    make_standard_evaluador_mock_client,
    make_standard_orquestador_mock_client,
    make_standard_preparador_mock_client,
)


class MockOCRForBaseline:
    """Servidor OCR simulado con texto ficticio y advertencias determinísticas."""
    is_available: bool = True
    initialization_error: Optional[str] = None

    def __init__(self, text: str, url_warnings: Optional[List[Dict[str, str]]] = None) -> None:
        self.text = text
        self.url_warnings = url_warnings or []
        self.is_available = True
        self.initialization_error = None

    def extract_text(self, image: Any) -> Dict[str, Any]:
        return {
            "success": True,
            "text": self.text,
            "char_count": len(self.text),
            "word_count": len(self.text.split()),
            "url_warnings": self.url_warnings,
            "language_used": "spa+eng",
            "error": None,
        }


def make_dummy_png_bytes() -> bytes:
    """Crea una imagen PNG ficticia de 10x10 píxeles en memoria."""
    img = Image.new("RGB", (10, 10), color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def run_scenario(
    scenario_id: str,
    scenario_name: str,
    request: AgentInputRequest,
    ocr_service: Optional[Any] = None,
    requested_urls_for_enlaces: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Ejecuta un escenario individual con colectores de contexto para todos los agentes."""
    collector = ContextRecordingCollector()
    input_mode = request.input_mode

    # Envolver cada cliente simulado con el registrador de contexto para su agente
    orq_client = ContextRecordingClientWrapper(
        inner_client=make_standard_orquestador_mock_client(input_mode),
        collector=collector,
        agent_name="orquestador",
    )
    prep_client = ContextRecordingClientWrapper(
        inner_client=make_standard_preparador_mock_client(input_mode),
        collector=collector,
        agent_name="preparador",
    )
    msg_client = ContextRecordingClientWrapper(
        inner_client=make_standard_analizador_mensajes_mock_client(parallel_in_one_turn=True),
        collector=collector,
        agent_name="analizador_mensajes",
    )
    url_client = ContextRecordingClientWrapper(
        inner_client=make_standard_analizador_enlaces_mock_client(requested_urls_for_enlaces),
        collector=collector,
        agent_name="analizador_enlaces",
    )
    eval_client = ContextRecordingClientWrapper(
        inner_client=make_standard_evaluador_mock_client(generate_pdf=False, save_to_output=False),
        collector=collector,
        agent_name="evaluador",
    )

    orq = OrquestadorAgent(
        orquestador_llm_client=orq_client,
        preparador_llm_client=prep_client,
        analizador_mensajes_llm_client=msg_client,
        analizador_enlaces_llm_client=url_client,
        evaluador_llm_client=eval_client,
        ocr_service_override=ocr_service,
    )

    resp = orq.run(request)
    if resp.status != "success":
        raise RuntimeError(f"Fallo en escenario {scenario_id}: {resp.error_message}")

    summary = collector.get_summary()
    return {
        "scenario_id": scenario_id,
        "scenario_name": scenario_name,
        "input_mode": input_mode,
        "agents_involved": list(summary["by_agent"].keys()),
        "total_simulated_turns": summary["total_turns"],
        "accumulated_request_chars": summary["accumulated_request_chars"],
        "accumulated_request_bytes_utf8": summary["accumulated_request_bytes_utf8"],
        "by_agent": summary["by_agent"],
        "snapshots": summary["snapshots"],
    }


def main() -> int:
    print("=" * 80)
    print("MEDICIÓN Y LÍNEA BASE REPRODUCIBLE DE CONTEXTO ENVIADO AL MODELO")
    print("Aclaración obligatoria: Estos resultados describen los recorridos programados")
    print("del cliente simulado; no demuestran cuántos turnos ni tokens usará Gemini real.")
    print("=" * 80)

    scenarios_data = []

    # -------------------------------------------------------------------------
    # Escenario 1: Texto sin enlaces
    # -------------------------------------------------------------------------
    scen1_text = (
        "Estimado cliente: le informamos que su pedido #48921 ya se encuentra listo para "
        "retiro en nuestra sucursal de Av. Corrientes 1234 de lunes a viernes de 9 a 18 hs. "
        "Debe presentarse con su documento nacional de identidad."
    )
    req1 = AgentInputRequest(input_mode="text", text_content=scen1_text)
    res1 = run_scenario(
        scenario_id="ESC-01",
        scenario_name="Texto sin enlaces",
        request=req1,
    )
    scenarios_data.append(res1)

    # -------------------------------------------------------------------------
    # Escenario 2: Texto con dos enlaces ficticios
    # -------------------------------------------------------------------------
    scen2_text = (
        "Alerta de Seguridad Banco Ficticio: Detectamos un acceso sospechoso a su cuenta online. "
        "Para evitar la suspensión preventiva por 48 horas, valide su identidad en: "
        "https://banco-seguro-falso.com/login o acceda al portal de sorteos en "
        "https://promo-aniversario-falsa.xyz/premio para validar sus puntos."
    )
    req2 = AgentInputRequest(input_mode="text", text_content=scen2_text)
    res2 = run_scenario(
        scenario_id="ESC-02",
        scenario_name="Texto con dos enlaces ficticios",
        request=req2,
        requested_urls_for_enlaces=["URL-1", "URL-2"],
    )
    scenarios_data.append(res2)

    # -------------------------------------------------------------------------
    # Escenario 3: Captura con OCR simulado y enlace
    # -------------------------------------------------------------------------
    scen3_ocr_text = (
        "Notificación Judicial Ficticia: Se encuentra intimado a regularizar su deuda bancaria. "
        "Evite el embargo judicial de haberes ingresando inmediatamente a: "
        "https://portal-deuda-ficticio.online/pagar dentro de las próximas 2 horas."
    )
    mock_ocr = MockOCRForBaseline(
        text=scen3_ocr_text,
        url_warnings=[{"snippet": "portal-deuda-ficticio.online", "explanation": "Dominio .online extraído por OCR"}],
    )
    req3 = AgentInputRequest(
        input_mode="ocr_screenshot",
        image_bytes=make_dummy_png_bytes(),
        image_filename="captura_intimacion_ficticia.png",
    )
    res3 = run_scenario(
        scenario_id="ESC-03",
        scenario_name="Captura con OCR simulado y enlace",
        request=req3,
        ocr_service=mock_ocr,
        requested_urls_for_enlaces=["URL-1"],
    )
    scenarios_data.append(res3)

    # -------------------------------------------------------------------------
    # Presentación estructurada en terminal
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("RESUMEN DE LÍNEA BASE POR ESCENARIO:")
    print("-" * 80)

    for sc in scenarios_data:
        print(f"\n[{sc['scenario_id']}] {sc['scenario_name']} (input_mode: {sc['input_mode']})")
        print(f"  • Agentes intervinientes: {', '.join(sc['agents_involved'])}")
        print(f"  • Turnos simulados totales: {sc['total_simulated_turns']}")
        print(f"  • Contexto acumulado enviado: {sc['accumulated_request_chars']:,} caracteres | {sc['accumulated_request_bytes_utf8']:,} bytes UTF-8")
        print("  • Desglose por agente:")
        for ag_name, ag_info in sc["by_agent"].items():
            print(
                f"    - {ag_name:<20}: {ag_info['turns_count']} llamadas | "
                f"{ag_info['total_chars']:,} chars | {ag_info['total_bytes_utf8']:,} bytes UTF-8"
            )

    # Guardar línea base en docs/context_baseline_metrics.json
    output_path = PROJECT_ROOT / "docs" / "context_baseline_metrics.json"
    baseline_payload = {
        "metadata": {
            "title": "Línea Base Reproducible de Contexto Efectivamente Enviado",
            "version": "3.0",
            "methodology": "Simulación determinística de clientes LLM sin consumo de red ni datos reales",
            "unit_of_measurement": "Caracteres (len(str)) y Bytes UTF-8 (len(str.encode('utf-8')))",
            "disclaimer": (
                "Aclaración obligatoria: Estos resultados describen los recorridos programados "
                "del cliente simulado; no demuestran cuántos turnos ni tokens usará Gemini real."
            ),
        },
        "scenarios": scenarios_data,
    }

    output_path.write_text(json.dumps(baseline_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[OK] Línea base guardada en: {output_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
