# Políticas Declaradas y Controles Efectivos de Seguridad

Este documento describe la trazabilidad técnica de las políticas definidas en [`config/policy.json`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/config/policy.json), contrastando las declaraciones de configuración con su aplicación efectiva en el código fuente, herramientas, orquesta de agentes y contenedor Docker.

---

## 1. Matriz de Trazabilidad de Políticas y Controles

| Política / Clave en `config/policy.json` | Alcance | Archivo y Función Aplicadora | Estado de Implementación | Limitaciones Relevantes |
| :--- | :--- | :--- | :--- | :--- |
| **`runtime_constraints.allow_network: false`** | Orquesta / Herramientas / Contenedor | *Ninguno (no se evalúa en Python)* | **Solo declarativo** | No bloquea sockets a nivel de sistema operativo ni SO. Si bien las herramientas Python y el análisis de URLs operan localmente sin conexiones externas, la orquesta de agentes sí utiliza red para comunicarse con la API de Google Gemini. Solo la ejecución en Docker con `--network none` o reglas de firewall externas garantizan aislamiento de red estricto. |
| **`runtime_constraints.allow_shell_execution: false`** | Aplicación general | *Ninguno (no se evalúa en Python)* | **Solo declarativo** | El código de la aplicación no invoca llamadas a shell (`subprocess`, `os.system`), pero no existe un sandbox que lo bloquee en tiempo de ejecución a partir de esta directiva. En Docker, se ejecuta con usuario no privilegiado (`user: "10001:10001"`). |
| **`runtime_constraints.max_input_chars: 15000`** | Motor local / Preparador / Web | [`agents/tools/preparation_tools.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/agents/tools/preparation_tools.py) (`execute_tool_validar_entrada`)<br>[`scripts/worker.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/scripts/worker.py) (`run_pipeline`)<br>[`web/analysis_adapter.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/web/analysis_adapter.py) (`analyze_text`) | **Aplicado** | Rechaza de forma determinística cualquier entrada que supere los 15.000 caracteres antes de su procesamiento. |
| **`runtime_constraints.max_file_size_kb: 256`** | CLI / Worker | [`scripts/worker.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/scripts/worker.py) (`validate_file_path`) | **Aplicado (CLI/Worker)** / *No aplica en Web* | Limita el tamaño de archivos leídos desde disco en línea de comandos. En la web se gestiona mediante Streamlit y validación de texto en memoria. |
| **`runtime_constraints.allowed_extensions: [".txt"]`** | CLI / Worker | [`scripts/worker.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/scripts/worker.py) (`validate_file_path`) | **Aplicado (CLI/Worker)** | Restringe la lectura local a archivos con extensión `.txt`. |
| **`runtime_constraints.allowed_directories: ["examples"]`** | CLI / Worker | [`scripts/worker.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/scripts/worker.py) (`validate_file_path`) | **Aplicado (CLI/Worker)** | Asegura que el pipeline de CLI solo lea archivos dentro del directorio `examples/`. |
| **`runtime_constraints.save_user_messages: false`** | Trazas / Auditoría / Reportes | [`agents/common/traceability.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/agents/common/traceability.py) (`AgentTracer.record`)<br>[`scripts/report_generator.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/scripts/report_generator.py) | **No consultado en runtime (comportamiento fijado en código)** | La clave **no es leída ni evaluada** por el código en tiempo de ejecución. La exclusión del texto del mensaje en las trazas técnicas de auditoría proviene exclusivamente del código estático de `AgentTracer.record()`. Por otro lado, la exportación explícita de informes solicitada por el usuario (`output/informe_detective.*`) incluye intencionalmente extractos del mensaje y hallazgos como parte del documento entregable. |
| **`security.treat_input_as_untrusted: true`** | Prompts / Guardrails | [`agents/*/prompts.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/agents/) (Instrucciones de sistema)<br>Contratos Python (`ContractValidationError`) | **Aplicado (vía Prompt Engineering y Contratos)** / *Declarativo en policy.json* | La directiva no se consulta en código; se implementa delimitando entradas (`<untrusted_urls>`, `<untrusted_message>`) y validando esquemas estrictos de argumentos en cada herramienta. |
| **`security.ignore_embedded_instructions: true`** | Prompts / Guardrails | [`agents/*/prompts.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/agents/) | **Aplicado (vía Prompt Engineering)** / *Declarativo en policy.json* | Se instruye a los modelos a ignorar órdenes dirigidas al sistema. La detección determinística identifica intentos de inyección (`REGLA-MENSAJE-INYECCION-01`), pero no existe un filtro léxico que elimine previamente el texto antes de invocar a Gemini. |
| **`security.mask_sensitive_information: true`** | Privacidad / Sanitización | [`agents/common/privacy.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/agents/common/privacy.py)<br>[`agents/tools/url_analysis_tools.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/agents/tools/url_analysis_tools.py) | **Aplicado (en intercambio con LLM)** / *Declarativo en policy.json* | El booleano no se lee en tiempo de ejecución, pero la sanitización se ejecuta incondicionalmente en las entradas y salidas de herramientas enviadas a Gemini, enmascarando credenciales, tarjetas, CBU/CVU y tokens de URL con `[VALOR_URL_OCULTO]`. En memoria local, la evidencia literal se preserva para auditoría. |
| **`security.prohibit_dynamic_code_exec: true`** | Aplicación general | *Ninguno (no se evalúa en Python)* | **Solo declarativo** | El proyecto no utiliza `eval()`, `exec()` ni `compile()` para entradas del usuario. La directiva documenta la política pero no existe una barrera de ejecución dinámica basada en este flag. |
| **`security.block_path_traversal: true`** | CLI / Carga de Skills | [`scripts/worker.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/scripts/worker.py) (`validate_file_path`)<br>[`agents/common/skill_loader.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/agents/common/skill_loader.py) (`load_skill`) | **Aplicado (en código específico)** / *Declarativo en policy.json* | Se aplica mediante validaciones de ruta (`resolve().is_relative_to()` y bloqueo de `..`, `/`, `\`), sin consultar el valor del JSON. |
| **`weights.*` (8 ponderaciones)** | Motor determinístico / Evaluador | [`scripts/risk_classifier.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/scripts/risk_classifier.py)<br>[`agents/tools/evaluation_tools.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/agents/tools/evaluation_tools.py) (`execute_tool_calcular_puntaje`) | **Aplicado** | Los pesos se leen dinámicamente de `policy["weights"]` permitiendo calibrar la acumulación de severidad heurística. |
| **`thresholds.*` (umbral alto, medio, bajo)** | Motor determinístico / Evaluador | [`scripts/risk_classifier.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/scripts/risk_classifier.py)<br>[`agents/tools/evaluation_tools.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/agents/tools/evaluation_tools.py) (`execute_tool_asignar_nivel_riesgo`) | **Aplicado** | Los umbrales numéricos (50 para ALTO, 20 para MEDIO, 0 para BAJO) se leen directamente de `policy["thresholds"]`. |

---

## 2. Distinción entre Niveles de Coherencia y Control

Para evitar interpretaciones equívocas sobre el alcance de las políticas y su implementación:

1. **Coherencia Comprobada entre Herramientas (100% Verificada):**
   Existe coincidencia exacta y automatizada ([`tests/test_agents_tools_coherence.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/tests/test_agents_tools_coherence.py), control D3) entre:
   - Las declaraciones de herramientas expuestas al LLM en `prompts.py` (`TOOL_DECLARATIONS`).
   - Las implementaciones registradas en `TOOL_REGISTRY`.
   - Las herramientas explícitamente autorizadas en `run_agent_tool_loop` de los 5 agentes.
   Esta correspondencia está garantizada por pruebas unitarias parametrizadas continuas sin discrepancias.

2. **Opciones Declarativas de `policy.json` (No Consultadas en Ejecución):**
   Campos como `allow_network`, `allow_shell_execution`, `prohibit_dynamic_code_exec`, `treat_input_as_untrusted`, `ignore_embedded_instructions`, `mask_sensitive_information`, `block_path_traversal` y `save_user_messages` **no son leídos ni evaluados por el intérprete de Python**. Actúan como documentación formal y especificación de diseño para auditorías externas, no como interruptores dinámicos del sistema.

3. **Controles de Seguridad Efectivos en Código:**
   Los controles de mitigación están implementados directamente en la lógica estática de Python de manera incondicional:
   - Enmascaramiento y sanitización de parámetros sensibles y credenciales en [`agents/common/privacy.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/agents/common/privacy.py).
   - Validación estricta de esquemas y tipos mediante contratos [`agents/common/contracts.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/agents/common/contracts.py) (`ContractValidationError`).
   - Límites determinísticos de longitud en [`agents/tools/preparation_tools.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/agents/tools/preparation_tools.py).
   - Omisión de contenido textual del usuario en [`agents/common/traceability.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/agents/common/traceability.py) (`AgentTracer`).
   - Bloqueo de recorridos de ruta en [`agents/common/skill_loader.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/agents/common/skill_loader.py).
   Estos controles operan con independencia del estado o presencia de los flags de `policy.json`.

---

## 3. Aclaraciones de Seguridad y Entorno Operativo

1. **Análisis Estático de URLs (Zero Network):**
   El análisis de direcciones web implementado en [`scripts/url_analyzer.py`](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/scripts/url_analyzer.py) y consumido por `tool_analizar_url` es **100% estático**. Descompone la sintaxis mediante `urllib.parse` e inspecciona patrones de dominio, TLD, IP y credenciales sin realizar consultas DNS, pings ni peticiones HTTP.
2. **Uso de Red por la Orquesta:**
   A diferencia del motor local determinístico (que puede correr de forma totalmente desconectada), la **Orquesta de Agentes** sí requiere acceso a internet para comunicarse vía HTTPS con los endpoints de la API de Google Gemini. La presencia de `allow_network: false` en `policy.json` es declarativa y no restringe las conexiones salientes del SDK `google-genai`.
3. **Validez del Aislamiento de Red:**
   Una prueba que verifique que no se importan librerías como `urllib.request` o `requests` dentro de `url_analyzer.py` demuestra que ese script no las usa, pero **no constituye una prueba de aislamiento de red a nivel de proceso o contenedor**. El aislamiento estricto de red se verifica exclusivamente mediante la ejecución en Docker con `--network none`.
4. **Tratamiento de Mensajes y Persistencia (`save_user_messages`):**
   El valor de `runtime_constraints.save_user_messages: false` en `policy.json` **no es consultado por el código**. El comportamiento observado se descompone en dos aspectos técnicos independientes:
   - **Trazas técnicas de auditoría (`AgentTracer`):** La lógica fija de `AgentTracer.record` almacena únicamente metadatos operacionales (tipo de evento, marcas temporales, conteo de tokens o indicadores y nombres de agentes), omitiendo intencionalmente el texto del usuario de los registros de telemetría.
   - **Exportación explícita de informes (`ReportGenerator` / `tool_generar_pdf`):** Diseñada de forma deliberada para persistir en disco (`output/informe_detective.*`) el documento solicitado por el usuario, conteniendo el texto analizado, el veredicto y las recomendaciones preventivas. No está sujeta ni restringida por el flag declarativo.

---

## 4. Documentación Técnica de Referencia Humana

Para los desarrolladores y auditores humanos que requieran consultar el catálogo completo de reglas heurísticas y señales sintácticas, se mantienen los siguientes documentos de referencia:
- [Guía de Señales Sintácticas de URLs](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/references/url_signals_guide.md) (`references/url_signals_guide.md`): detalle técnico de `REGLA-URL-01` a `REGLA-URL-05`.
- [Guía de Detección de Phishing](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/references/phishing-guide.md) (`references/phishing-guide.md`).
- [Pautas de Seguridad](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/references/security-guidelines.md) (`references/security-guidelines.md`).

