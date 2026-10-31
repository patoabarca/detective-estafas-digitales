"""
Punto de Entrada Principal (Worker) para Detective de Estafas Digitales.

Coordina la validación segura de entradas, ejecución de analizadores estáticos,
clasificación explicable de riesgo y generación de informes (JSON y Markdown).

Principios de Seguridad Implementados:
- Control de desbordamiento / longitud máxima de entrada.
- Prevención estricta de Path Traversal y bloqueo de secretos.
- Entrada tratada como payload pasivo y no confiable (Anti-Prompt Injection).
- Cero conexiones de red (Zero Network).
- Sin llamadas dinámicas a shell ni evaluación de código (eval/exec prohibidos).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional

# Asegurar que el directorio de scripts esté en sys.path para importación robusta
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Importación de los módulos internos de scripts/
from analyzer import TextAnalyzer
from report_generator import ReportGenerator
from risk_classifier import RiskClassifier
from url_analyzer import analyze_urls_in_text

# Asegurar codificación UTF-8 en terminales y flujos de entrada/salida
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stdin and hasattr(sys.stdin, "reconfigure"):
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "policy.json"


def load_policy() -> Dict[str, Any]:
    """
    Carga la política de configuración de forma segura.
    Si el archivo no se encuentra, utiliza valores por defecto defensivos.
    """
    if CONFIG_PATH.is_file():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "runtime_constraints": {
            "max_input_chars": 15000,
            "max_file_size_kb": 256,
            "allowed_extensions": [".txt"],
            "allowed_directories": ["examples"],
        },
        "weights": {
            "prompt_injection_attempt": 45,
            "credential_harvesting": 40,
            "banking_threat_urgency": 35,
            "advance_fee_fraud": 35,
            "suspicious_url": 30,
            "urgency_generic": 15,
            "unverified_entity_impersonation": 15,
            "debin_or_transfer_trick": 30,
        },
        "thresholds": {"alto": 50, "medio": 20, "bajo": 0},
    }


def validate_file_path(requested_path: str, policy: Dict[str, Any]) -> Path:
    """
    Valida y resuelve una ruta de archivo aplicando defensas estrictas contra
    Path Traversal, fuga de secretos y extensiones no autorizadas.
    """
    constraints = policy.get("runtime_constraints", {})
    allowed_dirs = constraints.get("allowed_directories", ["examples"])
    allowed_exts = tuple(constraints.get("allowed_extensions", [".txt"]))
    max_size_kb = constraints.get("max_file_size_kb", 256)

    # 1. Bloqueo de nombres de archivos sensibles conocidos
    target_name = Path(requested_path).name.lower()
    sensitive_targets = {"id_rsa", "id_ed25519", "credentials.json", "policy.json", "config.json"}
    if (
        target_name.startswith(".env")
        or target_name in sensitive_targets
        or target_name.endswith((".pem", ".key", ".crt", ".log"))
    ):
        raise PermissionError(f"Acceso denegado: el archivo '{target_name}' está clasificado como sensible y protegido.")

    # 2. Resolución de la ruta canónica absoluta
    path_obj = Path(requested_path)
    if not path_obj.is_absolute():
        path_obj = (BASE_DIR / path_obj).resolve()
    else:
        path_obj = path_obj.resolve()

    # 3. Verificación de Jail / Frontera autorizada (Path Traversal check)
    is_in_allowed_dir = False
    for allowed_dir_name in allowed_dirs:
        allowed_dir_path = (BASE_DIR / allowed_dir_name).resolve()
        try:
            if path_obj.is_relative_to(allowed_dir_path):
                is_in_allowed_dir = True
                break
        except AttributeError:
            try:
                path_obj.relative_to(allowed_dir_path)
                is_in_allowed_dir = True
                break
            except ValueError:
                continue

    if not is_in_allowed_dir:
        raise PermissionError(
            f"Violación de frontera de seguridad (Path Traversal detectado): "
            f"El archivo debe residir exclusivamente dentro de las carpetas autorizadas ({', '.join(allowed_dirs)})."
        )

    # 4. Comprobación de existencia
    if not path_obj.is_file():
        raise FileNotFoundError(f"El archivo especificado no existe o no es un archivo regular: {requested_path}")

    # 5. Verificación de extensión permitida
    if not path_obj.name.lower().endswith(allowed_exts):
        raise ValueError(f"Extensión no permitida. Solo se admiten archivos con extensiones: {', '.join(allowed_exts)}")

    # 6. Verificación de tamaño máximo
    file_size_kb = path_obj.stat().st_size / 1024
    if file_size_kb > max_size_kb:
        raise ValueError(f"El archivo excede el tamaño máximo permitido de {max_size_kb} KB (tamaño actual: {file_size_kb:.2f} KB).")

    return path_obj


def read_input(args: argparse.Namespace, policy: Dict[str, Any]) -> str:
    """
    Obtiene el texto de entrada a partir de los argumentos o de STDIN,
    aplicando validación de longitud máxima.
    """
    max_chars = policy.get("runtime_constraints", {}).get("max_input_chars", 15000)
    raw_content = ""

    if args.file:
        safe_path = validate_file_path(args.file, policy)
        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            raw_content = f.read()
    elif args.text:
        raw_content = args.text
    elif args.stdin or not sys.stdin.isatty():
        raw_content = sys.stdin.read()
    else:
        raise ValueError(
            "No se proporcionó ningún texto para analizar. Utilice --text, --file o pase la entrada por STDIN."
        )

    # Validación de longitud máxima en memoria
    if len(raw_content) > max_chars:
        raise ValueError(
            f"La longitud de entrada ({len(raw_content)} caracteres) excede el límite de seguridad de {max_chars} caracteres."
        )

    return raw_content


def run_pipeline(text: str, policy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Función de orquestación pura: recibe texto y retorna el reporte JSON estructurado.
    Ideal para invocación programática y pruebas automatizadas.
    """
    if policy is None:
        policy = load_policy()

    # 1. Analizador de patrones textuales e inyección de instrucciones
    text_analyzer = TextAnalyzer(policy)
    text_analysis = text_analyzer.analyze(text)

    # 2. Analizador estático de URLs sin conexión de red
    url_analyses = analyze_urls_in_text(text)

    # 3. Clasificación explicable de riesgo
    risk_classifier = RiskClassifier(policy)
    risk_data = risk_classifier.classify(text, text_analysis, url_analyses)

    # 4. Generación de reporte estructurado
    report_gen = ReportGenerator()
    return report_gen.generate_json_report(risk_data, text_analysis, url_analyses)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detective de Estafas Digitales - Motor de Análisis Estático y Seguro"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--text", type=str, help="Texto directo del mensaje a analizar")
    group.add_argument("--file", type=str, help="Ruta de un archivo .txt autorizado para analizar")
    group.add_argument("--stdin", action="store_true", help="Leer mensaje desde la entrada estándar (STDIN)")

    parser.add_argument("--json", action="store_true", help="Emitir resultado exclusivamente en formato JSON estructurado")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directorio opcional donde exportar los informes generados (reporte.json, reporte.md y reporte.pdf)",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Generar también el informe en formato PDF cuando se especifica --output-dir (o ruta de archivo con --pdf-out)",
    )
    parser.add_argument(
        "--pdf-out",
        type=str,
        default=None,
        help="Ruta opcional para guardar directamente el informe PDF generado",
    )

    args = parser.parse_args()
    policy = load_policy()

    try:
        content = read_input(args, policy)
        report = run_pipeline(content, policy)

        report_gen = ReportGenerator()
        human_report = report_gen.generate_human_readable_report(report)

        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(human_report)

        # Exportación opcional de informes al sistema de archivos (ej. volumen montado en Docker)
        if args.output_dir:
            out_dir = Path(args.output_dir).resolve()
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "informe_detective.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            (out_dir / "informe_detective.md").write_text(human_report, encoding="utf-8")
            if args.pdf or True:
                if str(BASE_DIR) not in sys.path:
                    sys.path.insert(0, str(BASE_DIR))
                from web.pdf_exporter import generate_pdf_report

                pdf_bytes = generate_pdf_report(report)
                (out_dir / "informe_detective.pdf").write_bytes(pdf_bytes)

        if args.pdf_out:
            pdf_path = Path(args.pdf_out).resolve()
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            if str(BASE_DIR) not in sys.path:
                sys.path.insert(0, str(BASE_DIR))
            from web.pdf_exporter import generate_pdf_report

            pdf_bytes = generate_pdf_report(report)
            pdf_path.write_bytes(pdf_bytes)

        return 0

    except (PermissionError, ValueError, FileNotFoundError) as client_err:
        err_response = {
            "status": "error",
            "error_type": client_err.__class__.__name__,
            "message": str(client_err),
        }
        if args.json:
            print(json.dumps(err_response, indent=2, ensure_ascii=False), file=sys.stderr)
        else:
            print(f"❌ Error de Validación de Seguridad: {client_err}", file=sys.stderr)
        return 1

    except Exception as internal_err:
        err_response = {
            "status": "error",
            "error_type": "InternalError",
            "message": "Ocurrió un error inesperado durante el procesamiento seguro.",
        }
        if args.json:
            print(json.dumps(err_response, indent=2, ensure_ascii=False), file=sys.stderr)
        else:
            print("❌ Error interno: No se pudo completar el análisis.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
