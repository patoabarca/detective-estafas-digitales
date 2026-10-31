"""
Cliente y Ejecutor Seguro de Llamadas a Herramientas con Google Gemini (`google-genai`).

Implementa:
- Verificación explícita de credenciales (`GEMINI_API_KEY`) y del SDK `google-genai`.
- Bucle real de invocación de funciones (`function_calls` -> ejecución Python validada -> `from_function_response`).
- Límites estrictos de seguridad:
  * Máximo de iteraciones / llamadas a herramientas por agente (`max_tool_calls`).
  * Tiempo máximo de ejecución total (`max_elapsed_seconds`) y timeout HTTP por llamada.
  * Límite de tamaño de respuesta (`max_output_tokens`).
  * Lista blanca cerrada de herramientas permitidas para cada agente.
  * Prohibición de interpretar texto libre como comandos ejecutables.
- Soporte para inyección de cliente simulado (`llm_client`) en pruebas automatizadas sin consumo de API.
"""

from __future__ import annotations

import os
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from agents.common.contracts import ContractValidationError
from agents.common.traceability import AgentTracer

try:
    from google import genai
    from google.genai import types as genai_types
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    genai = None  # type: ignore
    genai_types = None  # type: ignore
    GOOGLE_GENAI_AVAILABLE = False


DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
MAX_TOOL_CALLS_DEFAULT = 5
MAX_ELAPSED_SECONDS_DEFAULT = 25.0
MAX_OUTPUT_TOKENS_DEFAULT = 1024
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_local_env_file(env_path: Optional[Path] = None, override: bool = False) -> bool:
    """
    Carga de forma segura las variables definidas en el archivo `.env` de la raíz del proyecto
    en `os.environ` para ejecuciones locales, sin requerir dependencias externas ni sobrescribir
    variables ya definidas en el entorno (salvo que `override=True`).
    Nunca imprime ni registra los valores leídos.
    """
    if not override and os.environ.get("DETECTIVE_SKIP_DOTENV") == "1":
        return False

    target_path = env_path if env_path is not None else (PROJECT_ROOT / ".env")
    if not target_path.is_file():
        return False

    loaded_any = False
    try:
        raw_content = target_path.read_text(encoding="utf-8")
        for raw_line in raw_content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            val = val.strip()
            if len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
                val = val[1:-1].strip()
            if not key:
                continue
            # Si la variable no existe en os.environ (o está vacía y el archivo provee un valor), la asignamos
            if override or key not in os.environ or (not os.environ.get(key, "").strip() and val):
                os.environ[key] = val
                loaded_any = True
    except OSError:
        return False

    return loaded_any


class AgentConfigurationError(RuntimeError):
    """Falta de credenciales de IA (`GEMINI_API_KEY`) o paquete `google-genai` no instalado."""
    pass


class AgentExecutionError(RuntimeError):
    """Fallo de API externa, timeout o exceso en el límite de llamadas a herramientas."""
    pass


def get_agent_runtime_status() -> Dict[str, Any]:
    """
    Informa de manera transparente si el entorno tiene configurada la API de Gemini
    para ejecutar los agentes reales. Carga automáticamente `.env` local si existe.
    """
    load_local_env_file()
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    model_name = (os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL).strip()
    has_key = bool(api_key and len(api_key) >= 10 and api_key != "tu_api_key_aqui")

    return {
        "sdk_installed": GOOGLE_GENAI_AVAILABLE,
        "api_key_configured": has_key,
        "ready": bool(GOOGLE_GENAI_AVAILABLE and has_key),
        "provider": "Google Gemini API (google-genai)",
        "model": model_name,
    }


def create_gemini_client(api_key: Optional[str] = None, timeout_ms: int = 15000) -> Any:
    """
    Inicializa el cliente oficial `google.genai.Client` con timeout acotado.
    Nunca registra ni expone la clave en mensajes de error.
    """
    load_local_env_file()
    resolved_key = (api_key or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not resolved_key or resolved_key == "tu_api_key_aqui":
        raise AgentConfigurationError(
            "No se encontró la variable de entorno GEMINI_API_KEY configurada. "
            "Para usar el modo de Agentes IA, configurá GEMINI_API_KEY en el archivo .env o utilizá el Modo Local Determinístico."
        )

    if not GOOGLE_GENAI_AVAILABLE:
        raise AgentConfigurationError(
            "El SDK oficial 'google-genai' no está instalado en el entorno Python."
        )

    http_opts = genai_types.HttpOptions(timeout=timeout_ms)
    return genai.Client(api_key=resolved_key, http_options=http_opts)


def run_agent_tool_loop(
    agent_name: str,
    system_instruction: str,
    user_prompt: str,
    allowed_tools: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]],
    tool_declarations: List[Dict[str, Any]],
    tracer: AgentTracer,
    llm_client: Optional[Any] = None,
    model_name: Optional[str] = None,
    max_tool_calls: int = MAX_TOOL_CALLS_DEFAULT,
    max_elapsed_seconds: float = MAX_ELAPSED_SECONDS_DEFAULT,
) -> Dict[str, Any]:
    """
    Ejecuta el ciclo real de un agente con un modelo de IA y una lista cerrada de herramientas:
    1. Envía las instrucciones del agente, las declaraciones de herramientas autorizadas y el prompt.
    2. Si el modelo devuelve `function_calls`:
       - Verifica que el nombre de la función esté en `allowed_tools` (lista cerrada).
       - Ejecuta la herramienta Python validando estrictamente sus argumentos.
       - Registra el evento en `tracer` (sin secretos ni textos completos).
       - Devuelve el resultado al modelo como `function_response`.
    3. Finaliza cuando el modelo emite su respuesta final o se alcanza el límite de llamadas/tiempo.
    """
    load_local_env_file()
    resolved_model = (model_name or os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL).strip()
    client = llm_client if llm_client is not None else create_gemini_client()

    start_wall = time.monotonic()
    tool_calls_count = 0

    # Si estamos usando el cliente real de google-genai, construimos los objetos types.*
    use_genai_types = GOOGLE_GENAI_AVAILABLE and not hasattr(client, "is_mock_client")

    if use_genai_types:
        fn_decls = [
            genai_types.FunctionDeclaration(
                name=td["name"],
                description=td["description"],
                parameters=td.get("parameters"),
            )
            for td in tool_declarations
        ]
        tools_config = [genai_types.Tool(function_declarations=fn_decls)]
        config = genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=tools_config,
            temperature=0.0,
            max_output_tokens=MAX_OUTPUT_TOKENS_DEFAULT,
        )
        contents: List[Any] = [
            genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text=user_prompt)],
            )
        ]
    else:
        # Estructura neutral para clientes simulados en tests unitarios
        config = {
            "system_instruction": system_instruction,
            "tools": tool_declarations,
            "temperature": 0.0,
            "max_output_tokens": MAX_OUTPUT_TOKENS_DEFAULT,
        }
        contents = [{"role": "user", "parts": [{"text": user_prompt}]}]

    final_text = ""

    while True:
        elapsed = time.monotonic() - start_wall
        if elapsed > max_elapsed_seconds:
            tracer.record(
                agent=agent_name,
                event_type="agent_error",
                tool="none",
                status="error",
                detail=f"Tiempo máximo de ejecución excedido ({elapsed:.2f}s > {max_elapsed_seconds}s).",
                duration_ms=elapsed * 1000,
            )
            raise AgentExecutionError(
                f"El agente '{agent_name}' superó el tiempo máximo permitido de {max_elapsed_seconds}s."
            )

        try:
            response = client.models.generate_content(
                model=resolved_model,
                contents=contents,
                config=config,
            )
        except (AgentConfigurationError, AgentExecutionError, ContractValidationError):
            raise
        except Exception as api_exc:
            # Sanitizar cualquier posible aparición de clave en el mensaje de excepción
            err_msg = str(api_exc)
            api_key_val = os.environ.get("GEMINI_API_KEY", "")
            if api_key_val and len(api_key_val) > 4:
                err_msg = err_msg.replace(api_key_val, "[CLAVE_OCULTA]")
            tracer.record(
                agent=agent_name,
                event_type="agent_error",
                tool="llm_api",
                status="error",
                detail=f"Fallo en comunicación con API del modelo: {err_msg[:140]}",
                duration_ms=(time.monotonic() - start_wall) * 1000,
            )
            raise AgentExecutionError(f"Error al invocar el modelo de IA en '{agent_name}': {err_msg}") from api_exc

        # Extraer llamadas a herramientas de la respuesta del modelo
        fn_calls = getattr(response, "function_calls", None)
        if not fn_calls:
            final_text = (getattr(response, "text", "") or "").strip()[:4000]
            break

        # Agregar el turno del asistente al historial de conversación
        if use_genai_types and getattr(response, "candidates", None):
            contents.append(response.candidates[0].content)
        else:
            contents.append(
                {
                    "role": "model",
                    "function_calls": [
                        {"name": getattr(fc, "name", ""), "args": dict(getattr(fc, "args", {}) or {})}
                        for fc in fn_calls
                    ],
                }
            )

        response_parts: List[Any] = []

        for fc in fn_calls:
            tool_calls_count += 1
            if tool_calls_count > max_tool_calls:
                tracer.record(
                    agent=agent_name,
                    event_type="agent_error",
                    tool=str(getattr(fc, "name", "unknown")),
                    status="rejected",
                    detail=f"Límite máximo de llamadas a herramientas superado ({max_tool_calls}).",
                )
                raise AgentExecutionError(
                    f"El agente '{agent_name}' superó el límite máximo de {max_tool_calls} llamadas a herramientas."
                )

            fn_name = str(getattr(fc, "name", "") or "")
            raw_args = dict(getattr(fc, "args", {}) or {}) if getattr(fc, "args", None) is not None else {}

            # Verificar lista cerrada de herramientas permitidas para este agente
            if fn_name not in allowed_tools:
                tracer.record(
                    agent=agent_name,
                    event_type="tool_call",
                    tool=fn_name,
                    status="rejected",
                    detail=f"Herramienta '{fn_name}' bloqueada: no pertenece a la lista autorizada de '{agent_name}'.",
                )
                raise ContractValidationError(
                    f"Intento de llamada a herramienta no autorizada '{fn_name}' por el agente '{agent_name}'."
                )

            call_t0 = time.monotonic()
            try:
                tool_output = allowed_tools[fn_name](raw_args)
                call_ms = (time.monotonic() - call_t0) * 1000
                out_status = str(tool_output.get("status", "ok"))
                trace_status = "error" if out_status in ("tool_error", "error") else "ok"
                tracer.record(
                    agent=agent_name,
                    event_type="tool_call",
                    tool=fn_name,
                    status=trace_status,
                    detail=f"Ejecución de {fn_name} finalizada con status='{out_status}'.",
                    duration_ms=call_ms,
                )
            except ContractValidationError as val_err:
                call_ms = (time.monotonic() - call_t0) * 1000
                tracer.record(
                    agent=agent_name,
                    event_type="tool_call",
                    tool=fn_name,
                    status="rejected",
                    detail=f"Argumentos inválidos en '{fn_name}': {str(val_err)[:120]}",
                    duration_ms=call_ms,
                )
                raise

            if use_genai_types:
                response_parts.append(
                    genai_types.Part.from_function_response(
                        name=fn_name,
                        response={"result": tool_output},
                    )
                )
            else:
                response_parts.append(
                    {"function_response": {"name": fn_name, "response": {"result": tool_output}}}
                )

        if use_genai_types:
            contents.append(genai_types.Content(role="user", parts=response_parts))
        else:
            contents.append({"role": "user", "parts": response_parts})

    return {
        "final_text": final_text,
        "tool_calls_count": tool_calls_count,
        "model_used": resolved_model,
    }
