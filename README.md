# 🛡️ Detective de Estafas Digitales
## Skill de IA para Antigravity + Orquesta de Agentes IA (Etapa 1) + Mini Aplicación Web con OCR y Exportador PDF

Trabajo Práctico para la **Diplomatura en Inteligencia Artificial**.

---

## 📋 1. Resumen Ejecutivo y Objetivos

**Detective de Estafas Digitales** es una solución de ciberseguridad explicable diseñada para proteger a los usuarios frente a fraudes digitales cotidianos: **phishing, suplantación de identidad (spoofing), falso premio con pago anticipado, maniobras de DEBIN e ingeniería social**.

El proyecto nació como una Skill para agentes de inteligencia artificial en **Google Antigravity**, fue ampliado con una **mini aplicación web en Streamlit con OCR local** y ahora evoluciona hacia una **Orquesta de Agentes IA (Etapa 1)** que integra un **Agente Orquestador** y un **Agente Preparador** con llamadas reales a herramientas (`tool-calling`) sobre la API oficial de Google Gemini (`google-genai`), manteniendo intacto el **Modo Local Determinístico (Sin Red)**.

### Principios Rectores:
1. **Doble Modo en la App Web + Vía CLI:** La aplicación web permite alternar entre el **Modo Local Determinístico (Zero Network)** y el **Modo Orquesta de Agentes IA (Etapa 1: Orquestador + Preparador)**, reutilizando el mismo motor heurístico, el OCR local y el analizador estático de URLs sin duplicar lógica.
2. **Seguridad Ofensiva y Defensiva:** Trata cualquier mensaje ingresado o texto extraído como **información no confiable (Untrusted Data)**. Neutraliza intentos de **Prompt Injection / Jailbreak** y prohíbe la ejecución de comandos embebidos o herramientas fuera de la lista blanca de cada agente.
3. **Cero Visitas a Enlaces Sospechosos:** Tanto en el modo local como en el modo de agentes, el análisis de enlaces y dominios es 100% estático y local. **Nunca visita ni consulta las URLs del mensaje** (evitando ataques de tracking, Webhooks maliciosos o interacción con servidores atacantes).
4. **Visión por Computadora y OCR Local:** Procesamiento de capturas de pantalla en memoria RAM con Tesseract OCR local. En el modo de agentes, el Agente Preparador invoca la herramienta local `tool_extraer_texto_captura` sin enviar los bytes crudos de la imagen al proveedor externo.
5. **Revisión Humana Obligatoria (Human-in-the-loop):** Heurística preventiva de anomalías en URLs reconocidas por OCR (como confusión de `1` por `l` o `0` por `o`) con advertencias visuales y editor interactivo. Una captura ilegible produce estado `incompleto` (`texto_no_extraible`) y riesgo `INDETERMINADO` — nunca texto inventado ni riesgo `BAJO`.
6. **Clasificación Explicable (Sin Cajas Negras):** La determinación del nivel de riesgo se realiza mediante reglas ponderadas y documentadas (`config/policy.json`). Las puntuaciones representan una **escala heurística de severidad acumulada (0-100)** y **NO una probabilidad estadística**.
7. **Informes Descargables en PDF y Persistencia Local/Docker:** Exportación formal de informes generados en memoria con ReportLab para descarga por navegador o guardado en `output/`.

---

## 🏛️ 2. Arquitectura General: Modos de Ejecución y Orquesta de Agentes (Etapa 1)

El sistema implementa tres recorridos complementarios que comparten las mismas herramientas y el motor central:

```text
┌────────────────────────────────────────────────────────────────────────┐
│              VÍA 1: AGENTE EN IDE (ANTIGRAVITY + SKILL)                │
│                                                                        │
│   Usuario ➔ Antigravity ➔ SKILL.md ➔ scripts/worker.py (STDIN)         │
│   ➔ Motor Python ➔ JSON estructurado ➔ Explicación Empática            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│        VÍA 2A: APP WEB STREAMLIT - MODO LOCAL DETERMINÍSTICO           │
│                                                                        │
│   Usuario ➔ Streamlit (app.py) ➔ Texto / OCR (Tesseract local)         │
│   ➔ web/analysis_adapter.py ➔ Motor Python ➔ Informe Visual / PDF      │
│   (100% Offline / Zero Network: no requiere API key ni conexión)       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│     VÍA 2B: APP WEB STREAMLIT - MODO ORQUESTA DE AGENTES (ETAPA 1)     │
│                                                                        │
│   Streamlit (app.py)                                                   │
│     ➔ Sanitización preventiva de PII (CBU/CVU, DNI, tarjetas, etc.)    │
│     ➔ Agente Orquestador (agents/orquestador/ - Gemini Tool-Calling)   │
│         ├── Tool: delegar_preparacion                                  │
│         │     ➔ Agente Preparador (agents/preparador/)                 │
│         │         ├── Skill + Tool: validar-entrada                    │
│         │         ├── Skill + Tool: extraer-texto-captura (si imagen)  │
│         │         └── Skill + Tool: extraer-enlaces                    │
│         │     ➔ PreparationResult (estado, detalle_estado, enlaces)    │
│         └── Tool: ejecutar_motor_deterministico (si preparación OK)    │
│               ➔ web/analysis_adapter.py (reglas y puntaje intactos)    │
│     ➔ OrchestratorResponse + Trazabilidad de Agentes + Informe PDF     │
└────────────────────────────────────────────────────────────────────────┘
```

### Diferencia entre el Modo Local y el Modo con Agentes IA:
| Característica | Modo Local Determinístico | Modo Orquesta de Agentes IA (Etapa 1) |
| :--- | :--- | :--- |
| **Conexión de red** | **Cero (100% Offline / Zero Network)**. No realiza ninguna petición externa. | **Habilitada hacia el proveedor IA configurado** (`google-genai` / Gemini API). **Nunca visita las URLs sospechosas del mensaje.** |
| **Requisitos de credenciales** | Ninguno. Funciona sin `.env` ni claves. | Requiere `GEMINI_API_KEY` (y opcionalmente `GEMINI_MODEL`, por defecto `gemini-3.5-flash-lite`). |
| **Ejecución de OCR y URLs** | Local en memoria RAM (Pillow + Tesseract + `scripts/url_analyzer.py`). | Local en memoria RAM invocada mediante herramientas autorizadas por el **Agente Preparador**. |
| **Privacidad de datos** | El texto jamás sale de la máquina local o contenedor. | Se aplica **enmascaramiento preventivo de PII** (`agents/common/privacy.py`) antes de enviar texto al LLM externo, mostrando un aviso transparente en la UI. |
| **Fallo de API o falta de clave** | No aplica. | Informa el error de forma explícita (`estado="error"`), **sin simular** que los agentes se ejecutaron y permitiendo usar el Modo Local. |

> [!NOTE]
> **Alcance de la Etapa 1:** En esta primera etapa están implementados como agentes reales de IA el **Agente Orquestador** (`agents/orquestador/`) y el **Agente Preparador** (`agents/preparador/`). La evaluación de señales de fraude posterior a la preparación continúa utilizando el motor determinístico actual (`web/analysis_adapter.py` / `scripts/`) expuesto a través de la herramienta acotada `ejecutar_motor_deterministico`. Los agentes analistas especialistas se incorporarán en etapas posteriores.

---

## 🧩 2.1. Skills y Herramientas de la Orquesta (Etapa 1)

El repositorio cuenta con **4 Skills** en `.agents/skills/`, cuyas instrucciones y metadatos YAML son cargados y validados programáticamente en tiempo de ejecución por `agents/common/skill_loader.py`:

| Skill (`.agents/skills/<nombre>/SKILL.md`) | Agente Autorizado | Herramienta Python Asociada | Responsabilidad Única |
| :--- | :--- | :--- | :--- |
| `validar-entrada` | `preparador` | `tool_validar_entrada` (`agents/tools/preparation_tools.py`) | Validar tipo de entrada (`texto` o `captura`), longitud, formato binario (PNG/JPEG/WebP), tamaño (≤10 MB) y dimensiones (≤25 MP) reutilizando `scripts/worker.py` y `web/image_processor.py`. |
| `extraer-texto-captura` | `preparador` | `tool_extraer_texto_captura` (`agents/tools/preparation_tools.py`) | Preprocesar la captura y extraer texto con Tesseract OCR local + detectar distorsiones en URLs reutilizando `web/ocr_service.py`. |
| `extraer-enlaces` | `preparador` | `tool_extraer_enlaces` (`agents/tools/preparation_tools.py`) | Extraer URLs candidatas y auditarlas estáticamente sin visitar la red reutilizando `scripts/url_analyzer.py`. |
| `detective-estafas-digitales` | Agente IDE Antigravity | `scripts/worker.py` (CLI / STDIN) | Manifiesto integral para el análisis directo desde el chat de Antigravity IDE. |

Además, el **Agente Orquestador** (`orquestador`) tiene una lista cerrada de 2 herramientas registradas en `agents/orquestador/agent.py`:
- `delegar_preparacion`: Invoca al `PreparadorAgent` y devuelve el contrato estructurado `PreparationResult`.
- `ejecutar_motor_deterministico`: Invoca el motor determinístico (`analyze_text`) únicamente cuando `PreparationResult.estado == "correcto"`.

### Contrato `PreparationResult`:
El Agente Preparador devuelve siempre un objeto validado (`agents/common/contracts.py`) con:
- `estado`: `"correcto"` | `"incompleto"` | `"error"`
- `detalle_estado` (diferenciación explícita):
  - `"con_enlaces"`: Entrada válida con texto y al menos un enlace detectado.
  - `"sin_enlaces"`: Entrada válida con texto pero sin enlaces (`enlaces=[]`).
  - `"texto_no_extraible"`: Captura ilegible o sin texto reconocible por OCR (`estado="incompleto"`). Produce nivel de riesgo `INDETERMINADO` y exige revisión humana.
  - `"entrada_invalida"`: Entrada vacía, formato de imagen no soportado o exceso de tamaño/resolución (`estado="error"`).
  - `"fallo_herramienta"`: Error técnico en OCR, validación, modelo o configuración (`estado="error"`).

---

## 🏗️ 3. Estructura Modular del Proyecto

```text
detective-estafas-digitales/
│
├── README.md                         # Documentación integral, instalación y arquitectura de agentes
├── Dockerfile                        # Contenedor seguro (Motor CLI, App Web, Agentes, OCR y PDF)
├── compose.yaml                      # Orquestación con Docker Compose (puerto 8502->8501 y volumen ./output)
├── .env.example                      # Plantilla de variables de entorno (sin secretos reales)
├── requirements.txt                  # Dependencias del motor base (pytest - motor en stdlib pura)
├── requirements-web.txt              # Dependencias web y agentes (Streamlit, Pillow, Pytesseract, ReportLab, google-genai)
├── app.py                            # Punto de entrada de la aplicación web (Modo Local + Modo Orquesta IA)
│
├── .agents/                          # Skills del sistema (cargadas por Antigravity y por skill_loader.py)
│   └── skills/
│       ├── detective-estafas-digitales/
│       │   └── SKILL.md              # Skill principal para Antigravity IDE
│       ├── validar-entrada/
│       │   └── SKILL.md              # Skill del Preparador: validación de texto e imagen
│       ├── extraer-texto-captura/
│       │   └── SKILL.md              # Skill del Preparador: OCR local y anomalías en URLs
│       └── extraer-enlaces/
│           └── SKILL.md              # Skill del Preparador: extracción y auditoría estática de enlaces
│
├── agents/                           # Orquesta de Agentes IA - Etapa 1 (Orquestador + Preparador)
│   ├── common/
│   │   ├── contracts.py              # Contratos de datos (AgentInputRequest, PreparationResult, OrchestratorResponse)
│   │   ├── skill_loader.py           # Cargador y validador programático de SKILL.md y permisos por agente
│   │   ├── llm_client.py             # Ciclo real de tool-calling con google-genai, límites y timeouts
│   │   ├── privacy.py                # Enmascaramiento preventivo de PII antes de llamadas al LLM externo
│   │   └── traceability.py           # Registro auditable de eventos (AgentTracer y TraceEvent)
│   ├── tools/
│   │   └── preparation_tools.py      # Herramientas Python que envuelven scripts/ y web/ sin duplicar código
│   ├── preparador/
│   │   └── agent.py                  # Agente Preparador (PreparadorAgent) con contexto e instrucciones propias
│   └── orquestador/
│       └── agent.py                  # Agente Orquestador (OrquestadorAgent) que delega y coordina el flujo
│
├── scripts/                          # Motor determinístico funcional (Python 3.10+)
│   ├── worker.py                     # Punto de entrada seguro (CLI / STDIN / Pipeline)
│   ├── analyzer.py                   # Analizador heurístico de patrones e inyecciones de prompt
│   ├── url_analyzer.py               # Extracción y auditoría estática de URLs (IP, Punycode, Subdominios)
│   ├── risk_classifier.py            # Motor de clasificación de riesgo explicable (BAJO/MEDIO/ALTO/INDET)
│   └── report_generator.py           # Generador de reportes en JSON estructurado y Markdown
│
├── web/                              # Capa de presentación y servicios locales reutilizados
│   ├── analysis_adapter.py           # Adaptador seguro entre Streamlit/Agentes y scripts/
│   ├── image_processor.py            # Validación en memoria (anti Decompression Bombs) y preprocesamiento
│   ├── ocr_service.py                # Servicio local de Tesseract OCR y detección de distorsiones en URLs
│   ├── pdf_exporter.py               # Generación en memoria (BytesIO) de informes PDF con ReportLab
│   └── ui_helpers.py                 # Estilos CSS sobrios, tarjetas de riesgo y componentes visuales
│
├── config/                           # Parámetros y contratos de datos del motor
│   ├── policy.json                   # Políticas de ejecución, límites de tamaño y ponderaciones
│   └── result_schema.json            # Esquema JSON Schema del reporte final
│
└── tests/                            # Batería de 102 pruebas automatizadas con pytest
    ├── test_agents_orchestration.py  # 18 pruebas de Orquestador, Preparador, Skills, seguridad y límites
    └── ...                           # 84 pruebas existentes del motor, OCR, PDF, CLI, Docker y seguridad web
```

---

## ⚙️ 4. Instalación, Configuración y Puesta en Marcha

### Paso 1: Posicionarse en el proyecto y activar el entorno virtual
- **En Windows (PowerShell):**
  ```powershell
  cd "detective-estafas-digitales"
  python -m venv .venv
  .venv\Scripts\activate
  pip install -r requirements-web.txt
  ```
- **En Linux / macOS:**
  ```bash
  cd "detective-estafas-digitales"
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements-web.txt
  ```

### Paso 2: Configurar variables de entorno (Opcional para Modo Local / Requerido para Modo Agentes IA)
Podés copiar la plantilla `.env.example` o definir las variables en tu terminal antes de iniciar la aplicación:

- **En PowerShell (Windows):**
  ```powershell
  $env:GEMINI_API_KEY="tu_clave_de_gemini_aqui"
  $env:GEMINI_MODEL="gemini-3.5-flash-lite"
  ```
- **En Bash (Linux / macOS):**
  ```bash
  export GEMINI_API_KEY="tu_clave_de_gemini_aqui"
  export GEMINI_MODEL="gemini-3.5-flash-lite"
  ```
*(La aplicación también carga automáticamente el archivo `.env` local de la raíz si existe. Si no configurás `GEMINI_API_KEY`, el **Modo Local Determinístico** funciona al 100% y el **Modo Orquesta de Agentes IA** te informará claramente en pantalla que falta la credencial).*

### Paso 3: Iniciar la Aplicación Web en Streamlit (Ejecución Local)
```bash
streamlit run app.py --server.port 8502
```
Abrirá la interfaz en `http://localhost:8502` (o en el puerto por defecto de Streamlit si se omite `--server.port`).

---

## 🚀 5. Cómo Probar la Aplicación desde Streamlit

1. **Seleccionar el modo de operación (Barra lateral izquierda):**
   - **🔒 Modo Local Determinístico (Sin Red):** Ejecuta directamente el motor heurístico y el OCR local sin llamadas externas.
   - **🤖 Modo Orquesta de Agentes IA (Orquestador + Preparador):** Ejecuta el recorrido `Streamlit ➔ Orquestador ➔ Preparador ➔ Resultado de preparación ➔ Motor determinístico`.
2. **Probar en la pestaña "📝 Pegar Texto":**
   - Cargá un ejemplo desde el selector o pegá un mensaje con o sin enlaces y presioná **"🔍 Analizar Mensaje"**.
   - En el **Modo Orquesta de Agentes IA**, además del dictamen de riesgo, verás tres paneles desplegables adicionales:
     - **🧩 Resultado del Agente Preparador (Etapa 1):** Muestra `estado`, `detalle_estado`, cantidad de enlaces extraídos y advertencias.
     - **🛡️ Aviso de Privacidad (Datos enviados al proveedor IA):** Informa qué datos personales fueron enmascarados preventivamente antes de invocar la API.
     - **🕵️ Trazabilidad de la Orquesta (Agentes y Herramientas):** Tabla auditable con cada paso ejecutado (`agent_start`, `skill_loaded`, `llm_call`, `tool_call`, `agent_finish`), estado y duración en milisegundos.
3. **Probar en la pestaña "📷 Subir Captura (OCR)":**
   - Subí una imagen PNG/JPG/WebP (por ejemplo, `examples/captura_phishing_bancario.png`).
   - En el **Modo Orquesta de Agentes IA**, podés elegir:
     - **"🤖 Preparar y Analizar con Orquesta (Directo)"**: El Orquestador delega en el Preparador la validación binaria (`tool_validar_entrada`), la lectura OCR (`tool_extraer_texto_captura`) y la auditoría de enlaces (`tool_extraer_enlaces`), y luego evalúa el mensaje. Si la captura es ilegible, devuelve `estado="incompleto"` (`texto_no_extraible`) y riesgo `INDETERMINADO`.
     - **"🔍 Paso 1: Extraer Texto para Revisar (Human-in-the-loop)"**: Extrae el texto con OCR local, muestra advertencias de posibles distorsiones en URLs, permite editar el texto manualmente y luego enviarlo a analizar.
4. **Descargar o Guardar el Informe:**
   - Al pie de los resultados, usá **"📄 Descargar Informe Completo en PDF"** (descarga por navegador) o **"💾 Guardar Informe en Carpeta Local (output/)"** (guarda `.pdf` y `.json` en `output/`).

---

## 🐳 5.1. Ejecución con Docker y Docker Compose

El archivo `compose.yaml` levanta el servicio `detective-web` publicando el puerto `127.0.0.1:8502:8501` (`http://localhost:8502` en el anfitrión hacia el puerto `8501` en el que escucha Streamlit dentro del contenedor), corriendo con el usuario sin privilegios `10001:10001`, montando `./output` en `/app/output` y pasando de forma opcional las variables `GEMINI_API_KEY`, `GEMINI_MODEL` y `DETECTIVE_DIAGNOSTICS` si están definidas en el anfitrión o en un archivo `.env` local (excluido por `.gitignore` y `.dockerignore`).

### 1. Iniciar la aplicación con Docker Compose
```bash
# Construir e iniciar en segundo plano:
docker compose up --build -d

# Verificar el estado y los logs:
docker compose ps
docker compose logs
```
Luego abrí **`http://localhost:8502`** en tu navegador. Para usar el **Modo Orquesta de Agentes IA** dentro del contenedor, asegurate de tener `GEMINI_API_KEY` configurada en tu archivo `.env` local (o exportada en tu terminal) antes de ejecutar `docker compose up`.

### 2. Detener el servicio (conservando los informes en `./output`)
```bash
docker compose down
```

### 3. Ejecutar las pruebas automatizadas dentro del contenedor Docker
```bash
docker run --rm --network none --entrypoint pytest detective-estafas-digitales -v
```

---

## 🔒 6. Controles de Seguridad Aplicados en Código y sus Límites

La seguridad del sistema se aplica mediante validaciones determinísticas en Python y no depende únicamente de las instrucciones de texto dadas al modelo:

| Control de Seguridad | Implementación en Código Python | Límites y Consideraciones Técnicas |
| :--- | :--- | :--- |
| **Validación previa al modelo** | `validate_and_load_image` (`web/image_processor.py`) verifica magic bytes (PNG/JPEG/WebP), tamaño máximo (10 MB) y resolución máxima (25 Megapíxeles) **antes** de iniciar cualquier llamada al LLM. | Protege contra *Decompression Bombs* y archivos corruptos o ejecutables renombrados. |
| **Aislamiento de bytes crudos y textos** | `PreparationSessionContext` (`agents/tools/preparation_tools.py`) mantiene los bytes de la imagen y el texto en memoria local; el LLM solo intercambia parámetros de control validados. | Evita enviar imágenes crudas al proveedor externo y previene corrupción de payloads entre turnos. |
| **Listas cerradas de herramientas y permisos por Skill** | `skill_loader.py` verifica que el agente esté en `allowed_agents` del `SKILL.md`. `run_agent_tool_loop` (`llm_client.py`) rechaza cualquier herramienta fuera del registro explícito del agente. | Ningún agente tiene acceso a shell, sistema de archivos arbitrario, ejecución de código ni navegación web. |
| **Validación estricta de argumentos** | `validate_tool_arguments` (`agents/common/contracts.py`) rechaza argumentos desconocidos, tipos inválidos, longitudes excesivas o valores fuera de enumeración antes de invocar la función Python. | El texto libre del modelo jamás se interpreta como comando ejecutable. |
| **Límites de llamadas, tiempo y tokens** | `run_agent_tool_loop` impone un máximo de llamadas a herramientas por turno (`max_tool_calls`), un presupuesto de tiempo total (`max_elapsed_seconds`) y un límite de tokens de salida (`max_output_tokens=1024`). | Mitiga bucles infinitos de agentes, denegación de servicio y consumo excesivo de cuota de API. |
| **Enmascaramiento preventivo de PII** | `sanitize_text_for_external_llm` (`agents/common/privacy.py`) enmascara CBU/CVU (22 dígitos), tarjetas (13-19 dígitos), CUIT/CUIL, DNI, correos y teléfonos antes de enviar texto al LLM externo, conservando las URLs para su análisis. | **Límite explícito:** El enmascaramiento por expresiones regulares reduce la exposición de datos sensibles frecuentes, pero **no garantiza la eliminación del 100% de los datos personales** en texto libre (por ejemplo, nombres propios o direcciones postales no estructuradas). La UI muestra siempre una advertencia transparente. |
| **Red del contenedor según el modo** | El motor CLI y las pruebas pueden ejecutarse con `--network none` (aislamiento total de red a nivel kernel). | **Límite explícito:** Cuando se ejecuta `docker compose up` para utilizar la aplicación web y la API de Gemini en el Modo Orquesta de Agentes IA, el contenedor dispone de salida de red general y **no está restringido a nivel de firewall de contenedor exclusivamente a la IP del proveedor de IA**, aunque el código Python jamás realiza peticiones HTTP a las URLs contenidas en los mensajes analizados. |

---

## 🧪 7. Pruebas Automatizadas (102 Tests en Total) y Validación Manual

El proyecto cuenta con **102 pruebas automatizadas con `pytest`** distribuidas en 12 archivos de prueba, cubriendo tanto el motor determinístico, el OCR, el exportador PDF y Docker como la nueva **Orquesta de Agentes IA (Etapa 1)** (`tests/test_agents_orchestration.py`):

```bash
.venv\Scripts\python.exe -m pytest -v
```

### Escenarios verificados en `tests/test_agents_orchestration.py` (18 tests):
1. Carga programática de `SKILL.md` (`validar-entrada`, `extraer-texto-captura`, `extraer-enlaces`) y bloqueo de agentes no autorizados o *path traversal* (3 tests).
2. Flujo completo `Orquestador ➔ Preparador ➔ Motor` para **texto con enlaces** (`estado="correcto"`, `detalle_estado="con_enlaces"`).
3. Flujo completo para **texto sin enlaces** (`estado="correcto"`, `detalle_estado="sin_enlaces"`, `enlaces=[]`).
4. Flujo completo para **captura legible con enlaces** (`estado="correcto"`, `detalle_estado="con_enlaces"`).
5. Flujo para **captura ilegible o en blanco** (`estado="incompleto"`, `detalle_estado="texto_no_extraible"`, nivel de riesgo `INDETERMINADO`, sin inventar texto ni clasificar como riesgo `BAJO`).
6. Rechazo de **entradas inválidas** (texto vacío, imagen corrupta o formato falso).
7. Contención de **Prompt Injection** en el contenido analizado sin desvío de herramientas.
8. Rechazo de **herramienta no permitida** solicitada por un modelo (`tool_call_rejected`).
9. Rechazo de **argumentos inválidos o inesperados** en llamadas a herramientas (`tool_args_invalid`).
10. Manejo explícito de **fallo técnico en la herramienta OCR** (`estado="error"`, `detalle_estado="fallo_herramienta"`).
11. Manejo explícito de **falta de credenciales (`GEMINI_API_KEY`) o fallo de API** con redacción de secretos en los mensajes de error.
12. Carga segura de `.env` local (`load_local_env_file`) sin sobrescribir variables ya definidas en el entorno.
13. Cumplimiento estricto del **límite máximo de llamadas a herramientas (`max_tool_calls`)** y del **presupuesto de tiempo (`max_elapsed_seconds`)**.
14. **Enmascaramiento preventivo de PII** (CBU/CVU, DNI, tarjeta, email) preservando URLs intactas y generación del **informe PDF** a partir del resultado orquestado.
15. Prueba de integración real contra la API de Google Gemini (`test_real_gemini_api_orchestration_when_configured`) verificada con `gemini-3.5-flash-lite` y datos ficticios (`PASSED`: 6 llamadas totales al modelo — 3 del Orquestador y 3 del Preparador — y 4 herramientas invocadas en orden: `delegar_preparacion` ➔ `tool_validar_entrada` ➔ `tool_extraer_enlaces` ➔ `ejecutar_motor_deterministico`).

### Resumen de Verificación Efectivamente Realizada (Etapa 1):
- **Suite determinística y con cliente LLM simulado (`pytest`):** `101 passed, 1 skipped` ejecutada tanto en el entorno virtual local de Windows como dentro del contenedor Docker (`docker exec detective-estafas-web pytest -v`).
- **Integración en vivo con Google Gemini API (`gemini-3.5-flash-lite`):** Verificada mediante `test_real_gemini_api_orchestration_when_configured` (`1 passed`) comprobando en las trazas la delegación real del Orquestador al Preparador, el uso de las herramientas autorizadas y el registro de tokens consumidos (`11.897` tokens de entrada + `438` tokens de salida = `12.335` tokens totales).
- **Comprobación manual en navegador (`http://localhost:8502`):** Verificada interactivamente sobre el contenedor levantado con Docker Compose seleccionando el **Modo Orquesta de Agentes IA (Orquestador + Preparador)**.

---

## ⚠️ 8. Honestidad Metodológica y Limitaciones

1. **Puntaje Heurístico (0-100):** Refleja la acumulación de indicadores de severidad identificados. **No representa una probabilidad matemática de fraude.**
2. **Ausencia de Señales != Mensaje Legítimo:** Que un mensaje obtenga **Riesgo BAJO (0/100)** indica que no se encontraron patrones conocidos, pero **no constituye un aval absoluto de autenticidad**.
3. **Captura Ilegible != Riesgo Bajo:** Si una imagen no contiene texto reconocible por OCR, el Preparador informa `estado="incompleto"` (`texto_no_extraible`) y el Orquestador asigna riesgo `INDETERMINADO`, solicitando revisión humana.
4. **Análisis Estático de Enlaces:** Por seguridad, el sistema nunca visita las URLs sospechosas ni resuelve redirecciones activas en acortadores como `bit.ly`.
5. **Enmascaramiento Heurístico de PII:** El filtro de privacidad enmascara patrones estructurados (CBU/CVU, tarjetas, DNI, CUIT/CUIL, emails y teléfonos), pero el usuario debe evitar enviar información confidencial no estructurada cuando utilice un proveedor externo de IA.

---

## 🎓 9. Materiales Oficiales para la Defensa Oral

- **Presentación Oficial (PowerPoint):** [Detective_Estafas_Digitales_Presentacion_FINAL.pptx](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/Detective_Estafas_Digitales_Presentacion_FINAL.pptx)
- **Guion de Defensa Oral (PDF):** [Guion_Defensa_Oral_Detective_Estafas_FINAL.pdf](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/Guion_Defensa_Oral_Detective_Estafas_FINAL.pdf)
- **Guion de Defensa Oral (Word):** [Guion_Defensa_Oral_Detective_Estafas_FINAL.docx](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/Guion_Defensa_Oral_Detective_Estafas_FINAL.docx)
- **Manual de la Aplicación Web:** [docs/manual_web.md](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/docs/manual_web.md)
