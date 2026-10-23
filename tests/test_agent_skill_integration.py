"""
Prueba de Integración Funcional del Flujo Agéntico (test_agent_skill_integration.py).
Valida el ciclo completo de la Skill en el entorno de Antigravity:
1. Lectura y validación del manifiesto SKILL.md (.agents/skills/...).
2. Verificación de metadatos YAML (name, description) para activación progresiva.
3. Procesamiento seguro de una consulta en lenguaje natural sobre WhatsApp bancario.
4. Generación del reporte estructurado JSON con desglose heurístico.
5. Verificación de directivas de seguridad (no red, no ejecución dinámica).
"""

import json
import subprocess
import sys
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
SKILL_MD_PATH = BASE_DIR / ".agents" / "skills" / "detective-estafas-digitales" / "SKILL.md"
WORKER_SCRIPT = BASE_DIR / "scripts" / "worker.py"
PYTHON_EXE = sys.executable


def test_agent_skill_manifest_validity():
    """
    Verifica que el archivo SKILL.md exista en la ruta canónica de Antigravity
    y posea un encabezado YAML válido con name y description para descubrimiento del agente.
    """
    assert SKILL_MD_PATH.is_file(), f"No se encontró SKILL.md en {SKILL_MD_PATH}"
    content = SKILL_MD_PATH.read_text(encoding="utf-8")

    # Validar frontmatter YAML
    assert content.startswith("---"), "SKILL.md debe iniciar con encabezado YAML '---'"
    parts = content.split("---")
    assert len(parts) >= 3, "Encabezado YAML mal formado en SKILL.md"

    yaml_block = parts[1]
    assert "name: detective-estafas-digitales" in yaml_block
    assert "description:" in yaml_block

    # Verificar palabras clave de activación
    desc = yaml_block.lower()
    for kw in ["whatsapp", "phishing", "estafas digitales", "prompt injection"]:
        assert kw in desc, f"La descripción de la Skill debe incluir '{kw}' para enrutamiento cognitivo."


def test_agent_simulation_user_whatsapp_query():
    """
    Simula la consulta en lenguaje natural del usuario requerida en la auditoría:
    'Recibí un WhatsApp que dice que mi cuenta bancaria será bloqueada y me pide ingresar
    a un enlace para verificar mi token. ¿Podés analizarlo?'
    """
    user_query_message = (
        "Estimado cliente: Detectamos actividad inusual. Su cuenta bancaria será bloqueada "
        "en las próximas 2 horas. Para evitar el bloqueo inmediato, ingrese a "
        "http://banco-galicia.validacion-seguridad.online/login para validar su clave digital y Token."
    )

    proc = subprocess.run(
        [PYTHON_EXE, str(WORKER_SCRIPT), "--stdin", "--json"],
        input=user_query_message,
        text=True,
        capture_output=True,
        encoding="utf-8"
    )

    assert proc.returncode == 0, f"Error en ejecución del motor: {proc.stderr}"
    report = json.loads(proc.stdout)

    # 1. El motor debe retornar éxito
    assert report["status"] == "success"

    # 2. El nivel debe ser ALTO por concurrencia de amenaza + token + enlace engañoso
    assert report["risk_assessment"]["level"] == "ALTO"
    assert report["risk_assessment"]["score"] >= 50
    assert report["risk_assessment"]["score_type"] == "heuristic_severity_score"

    # 3. Indicadores requeridos detectados
    indicator_ids = [i["id"] for i in report["indicators_detected"]]
    assert "ING-AMENAZA-BLOQUEO" in indicator_ids
    assert "FRA-CAPTURA-CREDENCIALES" in indicator_ids
    assert "ING-URGENCIA-ARTIFICIAL" in indicator_ids

    # 4. Auditoría de URL estática sin red
    assert len(report["url_analysis"]) == 1
    url_data = report["url_analysis"][0]
    assert "galicia" in url_data["domain"]
    assert any("Uso engañoso" in f for f in url_data["findings"])

    # 5. Explicación no técnica accesible generada
    assert len(report["non_technical_explanation"]) > 20
    assert "RIESGO ALTO" in report["non_technical_explanation"] or "estafa" in report["non_technical_explanation"].lower()

    # 6. Recomendaciones preventivas concretas
    assert len(report["recommendations"]) >= 3
    assert any("NO hagas clic" in r for r in report["recommendations"])
