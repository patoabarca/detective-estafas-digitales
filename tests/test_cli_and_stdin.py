"""
Pruebas de Interfaz CLI, STDIN y Manejo de Caracteres Especiales (test_cli_and_stdin.py).
Valida la invocación real del proceso worker.py mediante subproceso,
asegurando que el paso de texto arbitrario vía STDIN no se rompa con comillas,
caracteres especiales, saltos de línea ni textos en español.
"""

import json
import subprocess
import sys
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
PYTHON_EXE = sys.executable
WORKER_SCRIPT = BASE_DIR / "scripts" / "worker.py"


def test_cli_stdin_phishing_message():
    """
    Verifica que worker.py lea correctamente un mensaje de phishing a través de STDIN
    y emita el resultado en JSON con código de salida 0.
    """
    message = (
        "Estimado cliente de Banco Galicia: Su cuenta será suspendida en 2 horas por seguridad. "
        "Valide su token en https://galicia-validacion.seguridad-bancaria.online/login"
    )
    proc = subprocess.run(
        [PYTHON_EXE, str(WORKER_SCRIPT), "--stdin", "--json"],
        input=message,
        text=True,
        capture_output=True,
        encoding="utf-8"
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["status"] == "success"
    assert data["risk_assessment"]["level"] == "ALTO"
    assert data["risk_assessment"]["score"] >= 50
    assert data["risk_assessment"]["score_type"] == "heuristic_severity_score"


def test_cli_quotes_and_special_chars_via_stdin():
    """
    Verifica que textos con comillas dobles, comillas simples, saltos de línea,
    símbolos de moneda, tildes y caracteres especiales se procesen sin romperse.
    """
    complex_text = (
        "Hola! Me llegó este mensaje: \"URGENTE: Banco Santander informa que su cuenta 'premium' "
        "será bloqueada si no confirma su clave digital\".\n"
        "Link: http://santander.validacion-datos.online/login?token=abc123\n"
        "Costo de trámite: $0. ¡Evite el bloqueo inmediato!"
    )
    proc = subprocess.run(
        [PYTHON_EXE, str(WORKER_SCRIPT), "--stdin", "--json"],
        input=complex_text,
        text=True,
        capture_output=True,
        encoding="utf-8"
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["status"] == "success"
    assert data["risk_assessment"]["level"] in ("MEDIO", "ALTO")
    # Verificar que detectó el subdominio engañoso y la clave digital
    assert len(data["url_analysis"]) == 1
    assert any("santander" in f.lower() for f in data["url_analysis"][0]["findings"])


def test_cli_file_argument_execution():
    """
    Verifica la ejecución de worker.py pasando el argumento seguro --file.
    """
    example_path = "examples/phishing_bancario.txt"
    proc = subprocess.run(
        [PYTHON_EXE, str(WORKER_SCRIPT), "--file", example_path, "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(BASE_DIR)
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["status"] == "success"
    assert data["risk_assessment"]["level"] == "ALTO"


def test_cli_path_traversal_via_file_arg():
    """
    Verifica que el intento de Path Traversal vía CLI devuelva código de salida 1
    y un error controlado sin exponer trazas de la aplicación.
    """
    evil_path = "examples/../config/policy.json"
    proc = subprocess.run(
        [PYTHON_EXE, str(WORKER_SCRIPT), "--file", evil_path, "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(BASE_DIR)
    )
    assert proc.returncode == 1
    err_data = json.loads(proc.stderr)
    assert err_data["status"] == "error"
    assert err_data["error_type"] == "PermissionError"


def test_cli_empty_stdin_produces_indeterminado():
    """
    Verifica que pasar una entrada vacía por STDIN no arroje un fallo fatal,
    sino que clasifique controladamente como INDETERMINADO.
    """
    proc = subprocess.run(
        [PYTHON_EXE, str(WORKER_SCRIPT), "--stdin", "--json"],
        input="",
        text=True,
        capture_output=True,
        encoding="utf-8"
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["status"] == "success"
    assert data["risk_assessment"]["level"] == "INDETERMINADO"


def test_cli_missing_file_error():
    """
    Verifica que invocar worker.py con un archivo inexistente devuelva código 1 y error JSON.
    """
    proc = subprocess.run(
        [PYTHON_EXE, str(WORKER_SCRIPT), "--file", "examples/archivo_que_no_existe.txt", "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(BASE_DIR)
    )
    assert proc.returncode == 1
    err_data = json.loads(proc.stderr)
    assert err_data["status"] == "error"
    assert err_data["error_type"] == "FileNotFoundError"


def test_cli_excessive_input_via_stdin():
    """
    Verifica que enviar un flujo STDIN que supere 15.000 caracteres devuelva código 1 de error.
    """
    huge_input = "A" * 15500
    proc = subprocess.run(
        [PYTHON_EXE, str(WORKER_SCRIPT), "--stdin", "--json"],
        input=huge_input,
        text=True,
        capture_output=True,
        encoding="utf-8"
    )
    assert proc.returncode == 1
    err_data = json.loads(proc.stderr)
    assert err_data["status"] == "error"
    assert "excede el límite de seguridad" in err_data["message"]
