"""
Diagnóstico de los 8 Casos de Evaluación Manual.
Detective de Estafas Digitales.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.worker import run_pipeline, load_policy
from web.analysis_adapter import analyze_text

CASES_8 = [
    {
        "id": "Caso 1",
        "tipo": "Sospechoso",
        "name": "Paquete pendiente de entrega",
        "text": (
            "Hola, no pudimos entregar tu paquete porque falta validar el domicilio. "
            "El envío será devuelto al depósito al finalizar el día. Para reprogramar la entrega, "
            "confirmá tus datos y aboná el costo de gestión en https://entregas-confirmacion.paquetes-gestion.top"
        ),
    },
    {
        "id": "Caso 2",
        "tipo": "Sospechoso",
        "name": "Transferencia por error y solicitud DEBIN",
        "text": (
            "Hola! Te transferí por error $85.000 a tu cuenta en lugar de mi proveedor. "
            "Te acabo de enviar una solicitud de DEBIN para anular la transacción. "
            "Por favor aceptá el débito inmediato ahora mismo para que se me reembolse el dinero."
        ),
    },
    {
        "id": "Caso 3",
        "tipo": "Sospechoso",
        "name": "Amenaza de inhabilitación de cuenta y verificación",
        "text": (
            "Estimado usuario: detectamos actividad irregular en su cuenta. "
            "Por seguridad, el servicio permanecerá inhabilitado si no confirma su identidad antes del cierre de la jornada. "
            "Ingrese al centro de verificación y complete el procedimiento solicitado para continuar utilizando la plataforma."
        ),
    },
    {
        "id": "Caso 4",
        "tipo": "Sospechoso",
        "name": "Falso soporte técnico solicitando código SMS",
        "text": (
            "Buenas tardes, soy del soporte técnico. Detectamos un problema de sincronización con tu cuenta. "
            "Para resolverlo necesito que me compartas el código de seis dígitos que te acaba de llegar por SMS. "
            "No se lo pases a nadie más porque el código vence en cinco minutos."
        ),
    },
    {
        "id": "Caso 5",
        "tipo": "Legítimo",
        "name": "Aviso de mantenimiento programado",
        "text": (
            "Aviso de Sistemas: Este sábado entre las 02:00 y las 06:00 hs se realizará una ventana de mantenimiento "
            "programado en los servidores de correo y bases de datos. No se requerirá ninguna acción por parte de los usuarios."
        ),
    },
    {
        "id": "Caso 6",
        "tipo": "Legítimo",
        "name": "Recordatorio de vencimiento de documentación",
        "text": (
            "Estimado cliente: le recordamos que su póliza de seguro automotor vence el 30 del corriente mes. "
            "Para consultar las opciones de renovación o abonar su cuota habitual, ingrese a la app oficial de la aseguradora "
            "o comuníquese con su productor asesor."
        ),
    },
    {
        "id": "Caso 7",
        "tipo": "Legítimo",
        "name": "Capacitación sobre seguridad informática",
        "text": (
            "Invitación al Taller de Ciberseguridad Corporativa: Este jueves a las 15:00 hs conversaremos "
            "sobre buenas prácticas en contraseñas seguras, prevención de bloqueos de cuentas y detección de fraudes digitales. "
            "Los esperamos en el auditorio principal."
        ),
    },
    {
        "id": "Caso 8",
        "tipo": "Ambiguo",
        "name": "Actualización institucional de contactos",
        "text": (
            "Estimado colaborador: con motivo del inicio del ciclo anual, solicitamos verificar que su número telefónico "
            "y domicilio de contacto se encuentren correctamente actualizados en el sistema de legajos de la intranet corporativa."
        ),
    },
]


def run_diagnostics():
    policy = load_policy()
    print("=" * 80)
    print("DIAGNÓSTICO INICIAL DE LOS 8 CASOS DE EVALUACIÓN MANUAL")
    print("=" * 80)

    for c in CASES_8:
        report_direct = run_pipeline(c["text"], policy)
        report_adapter_text = analyze_text(c["text"], input_mode="text", custom_policy=policy)
        report_adapter_ocr = analyze_text(c["text"], input_mode="ocr_screenshot", custom_policy=policy)

        risk = report_direct["risk_assessment"]
        score = risk["score"]
        level = risk["level"]
        rules = risk["activated_rules"]
        indicators = [i["id"] for i in report_direct.get("indicators_detected", [])]

        # Verificar consistencia de modalidades
        assert report_direct["risk_assessment"]["score"] == report_adapter_text["risk_assessment"]["score"]
        assert report_adapter_text["risk_assessment"]["score"] == report_adapter_ocr["risk_assessment"]["score"]

        status_icon = "⚠️" if (c["tipo"] == "Sospechoso" and level == "BAJO") else "✅"
        print(f"\n{status_icon} [{c['id']}] {c['name']} ({c['tipo']})")
        print(f"   Puntaje: {score}/100 | Nivel: {level}")
        print(f"   Indicadores detectados ({len(indicators)}): {indicators}")
        print(f"   Reglas activadas ({len(rules)}): {rules}")
        if report_direct.get("url_analysis"):
            print(f"   URL Findings: {[u.get('findings') for u in report_direct['url_analysis']]}")


if __name__ == "__main__":
    run_diagnostics()
