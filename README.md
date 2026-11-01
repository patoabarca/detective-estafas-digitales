# 🛡️ Detective de Estafas Digitales
## Skill de IA para Antigravity + Orquesta de Agentes IA (Etapa 1 y Etapa 2) + Mini Aplicación Web con OCR y Exportador PDF

Trabajo Práctico para la **Diplomatura en Inteligencia Artificial**.

---

## 📋 1. Resumen Ejecutivo y Objetivos

**Detective de Estafas Digitales** es una solución de ciberseguridad explicable diseñada para proteger a los usuarios frente a fraudes digitales cotidianos: **phishing, suplantación de identidad (spoofing), falso premio con pago anticipado, maniobras de DEBIN e ingeniería social**.

El proyecto nació como una Skill para agentes de inteligencia artificial en **Google Antigravity**, fue ampliado con una **mini aplicación web en Streamlit con OCR local** y evoluciona hacia una **Orquesta de Agentes IA (Etapa 1 + Etapa 2)** que integra:
- **Agente Orquestador** (`agents/orquestador/`),
- **Agente Preparador** (`agents/preparador/`) con 3 skills de preparación, y
- **Agente Analizador de Mensajes** (`agents/analizador_mensajes/`) con 5 skills especializadas de detección lingüística,
ejecutándose mediante llamadas reales a herramientas (`tool-calling` y *parallel tool calling*) sobre la API oficial de Google Gemini (`google-genai`, modelo `gemini-3.5-flash-lite`), manteniendo intacto el **Modo Local Determinístico (Sin Red)** y la equivalencia exacta de puntuación.

### Principios Rectores:
1. **Doble Modo en la App Web + Vía CLI:** La aplicación web permite alternar entre el **Modo Local Determinístico (Zero Network)** y el **Modo Orquesta de Agentes IA (Orquestador + Preparador + Analizador de Mensajes)**, reutilizando las reglas del motor heurístico, el OCR local y el analizador estático de URLs sin duplicar lógica ni sumar dos veces una misma regla.
2. **Seguridad Ofensiva y Defensiva:** Trata cualquier mensaje ingresado o texto extraído como **información no confiable (Untrusted Data)**. Neutraliza intentos de **Prompt Injection / Jailbreak**, prohíbe la ejecución de comandos o herramientas fuera de la lista blanca de cada agente y verifica en código que todo fragmento de evidencia pertenezca literalmente al texto analizado (rechazo de evidencia inventada).
3. **Cero Visitas a Enlaces Sospechosos:** Tanto en el modo local como en el modo de agentes, el análisis de enlaces y dominios es 100% estático y local. **Nunca visita ni consulta las URLs del mensaje**.
4. **Visión por Computadora y OCR Local:** Procesamiento de capturas de pantalla en memoria RAM con Tesseract OCR local. En el modo de agentes, el Agente Preparador invoca la herramienta local `tool_extraer_texto_captura` sin enviar los bytes crudos de la imagen al proveedor externo.
5. **Revisión Humana Obligatoria (Human-in-the-loop):** Heurística preventiva de anomalías en URLs reconocidas por OCR con advertencias visuales y editor interactivo. Una captura ilegible o un análisis de mensaje con categorías omitidas produce estado `incompleto` y riesgo `INDETERMINADO` — nunca evidencia inventada ni riesgo `BAJO`.
6. **Clasificación Explicable (Sin Cajas Negras):** La determinación del nivel de riesgo se realiza mediante reglas ponderadas y documentadas (`config/policy.json`). Las puntuaciones representan una **escala heurística de severidad acumulada (0-100)** y **NO una probabilidad estadística**.
7. **Informes Descargables en PDF y Persistencia Local/Docker:** Exportación formal de informes generados en memoria con ReportLab para descarga por navegador o guardado en `output/`.

---

## 🏛️ 2. Arquitectura General: Modos de Ejecución y Orquesta de Agentes (Etapa 1 + Etapa 2)

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
│  VÍA 2B: APP WEB STREAMLIT - MODO ORQUESTA DE AGENTES (ETAPAS 1 y 2)   │
│                                                                        │
│   Streamlit (app.py)                                                   │
│     ➔ Sanitización preventiva de PII en texto, URLs y snippets         │
│     ➔ Agente Orquestador (agents/orquestador/ - Gemini Tool-Calling)   │
│         ├── 1. Tool: delegar_preparacion                               │
│         │     ➔ Agente Preparador (agents/preparador/)                 │
│         │         ├── Skill + Tool: validar-entrada                    │
│         │         ├── Skill + Tool: extraer-texto-captura (si imagen)  │
│         │         └── Skill + Tool: extraer-enlaces                    │
│         │     ➔ PreparationResult (estado, detalle_estado, enlaces)    │
│         ├── 2. Tool: delegar_analisis_mensaje (si preparación OK)      │
│         │     ➔ Agente Analizador de Mensajes                          │
│         │       (agents/analizador_mensajes/ - Parallel Tool-Calling)  │
│         │         ├── Skill + Tool: detectar-urgencia                  │
│         │         ├── Skill + Tool: detectar-amenazas                  │
│         │         ├── Skill + Tool: detectar-premios                   │
│         │         ├── Skill + Tool: detectar-pedidos-datos             │
│         │         └── Skill + Tool: detectar-pedidos-dinero            │
│         │     ➔ MessageAnalysisResult (5 categorías revisadas,         │
│         │       señales verificadas contra el texto original)          │
│         └── 3. Tool: ejecutar_motor_deterministico (si 5/5 revisadas)  │
│               ➔ TextAnalyzer.compose_analysis_from_agent_findings()    │
│                 (integra hallazgos sin reejecutar ni duplicar puntaje) │
│     ➔ OrchestratorResponse + Trazabilidad + Métricas + Informe PDF     │
└────────────────────────────────────────────────────────────────────────┘
```

### Diferencia entre el Modo Local y el Modo con Agentes IA:
| Característica | Modo Local Determinístico | Modo Orquesta de Agentes IA (Etapa 1 + Etapa 2) |
| :--- | :--- | :--- |
| **Conexión de red** | **Cero (100% Offline / Zero Network)**. No realiza ninguna petición externa. | **Habilitada hacia el proveedor IA configurado** (`google-genai` / Gemini API). **Nunca visita las URLs sospechosas del mensaje.** |
| **Requisitos de credenciales** | Ninguno. Funciona sin `.env` ni claves. | Requiere `GEMINI_API_KEY` (y `GEMINI_MODEL=gemini-3.5-flash-lite`). |
| **Ejecución de OCR, URLs y Detección de Señales** | Local en memoria RAM (`scripts/analyzer.py`, `scripts/url_analyzer.py`, `web/ocr_service.py`). | Orquestada mediante herramientas autorizadas por el **Agente Preparador** (3 skills) y el **Agente Analizador de Mensajes** (5 skills). |
| **Integración en la evaluación sin doble puntuación** | Ejecuta directamente `TextAnalyzer.analyze()`. | `TextAnalyzer.compose_analysis_from_agent_findings()` toma los hallazgos validados del `AnalizadorMensajesAgent` para las 5 categorías delegadas sin volver a correr esas detecciones y los entrega una sola vez a `RiskClassifier`. |
| **Privacidad de datos** | El texto jamás sale de la máquina local o contenedor. | Se aplica **enmascaramiento preventivo de PII** (`agents/common/privacy.py`) al texto enviado al LLM, a los parámetros sensibles de URLs y a las respuestas de herramientas que vuelven al modelo, conservando el original en memoria local. |
| **Fallo de API, categorías omitidas o falta de clave** | No aplica. | Si falta clave o falla una herramienta reporta `estado="error"`. Si faltan categorías obligatorias sin revisar reporta `estado="incompleto"` y riesgo `INDETERMINADO` (nunca `correcto` ni `BAJO`). |

---

## 🧩 2.1. Skills y Herramientas de la Orquesta (Etapas 1 y 2)

El repositorio cuenta con **9 Skills** en `.agents/skills/`, cuyas instrucciones y metadatos YAML son cargados y validados programáticamente en tiempo de ejecución por `agents/common/skill_loader.py`:

| Skill (`.agents/skills/<nombre>/SKILL.md`) | Agente Autorizado | Herramienta Python Asociada | Regla / Señal Asociada (`policy.json`) | Responsabilidad Única |
| :--- | :--- | :--- | :--- | :--- |
| `validar-entrada` | `preparador` | `tool_validar_entrada` | — | Validar tipo de entrada (`text` o `ocr_screenshot`), longitud, formato binario (PNG/JPEG/WebP), tamaño (≤10 MB) y dimensiones (≤25 MP). |
| `extraer-texto-captura` | `preparador` | `tool_extraer_texto_captura` | — | Preprocesar la captura y extraer texto con Tesseract OCR local + detectar distorsiones en URLs. |
| `extraer-enlaces` | `preparador` | `tool_extraer_enlaces` | `URL-*` | Extraer URLs candidatas y auditarlas estáticamente sin visitar la red. |
| `detectar-urgencia` | `analizador_mensajes` | `tool_detectar_urgencia` | `ING-URGENCIA-ARTIFICIAL` (`+15 pts`) | Detectar presión temporal, plazos perentorios o apuro deliberado (`_detect_urgency`). |
| `detectar-amenazas` | `analizador_mensajes` | `tool_detectar_amenazas` | `ING-AMENAZA-BLOQUEO` (`+35 pts`) | Detectar amenazas de bloqueo, suspensión, cierre de cuenta o embargo (`_detect_blocking_threats`). |
| `detectar-premios` | `analizador_mensajes` | `tool_detectar_premios` | `FRA-PREMIO-INESPERADO` (`+25 pts`) | Detectar sorteos falsos, premios inesperados o beneficios señuelo (`_detect_fake_rewards`). |
| `detectar-pedidos-datos` | `analizador_mensajes` | `tool_detectar_pedidos_datos` | `FRA-CAPTURA-CREDENCIALES` (`+40 pts`) | Detectar solicitudes de claves, contraseñas, tokens, códigos OTP/SMS o validación de identidad (`_detect_credential_harvesting`). |
| `detectar-pedidos-dinero` | `analizador_mensajes` | `tool_detectar_pedidos_dinero` | `FRA-PAGO-ANTICIPADO` (`+35 pts`) y `FRA-DEBIN-ENGANOSO` (`+30 pts`) | Detectar pedidos de pagos previos para liberar paquetes/premios (`_detect_advance_fee`) y maniobras de DEBIN o transferencias por error (`_detect_debin_trick`). |
| `detective-estafas-digitales` | Agente IDE Antigravity | `scripts/worker.py` (CLI / STDIN) | Todas las reglas del motor | Manifiesto integral para el análisis directo desde el chat de Antigravity IDE. |

Además, el **Agente Orquestador** (`orquestador`) tiene una lista cerrada de **3 herramientas** registradas en `agents/orquestador/agent.py`, cuyo orden obligatorio se hace cumplir en código Python:
1. `delegar_preparacion`: Invoca al `PreparadorAgent` y devuelve `PreparationResult`.
2. `delegar_analisis_mensaje`: Invoca al `AnalizadorMensajesAgent` únicamente si `PreparationResult.estado == "correcto"` y devuelve `MessageAnalysisResult`.
3. `ejecutar_motor_deterministico`: Invoca el motor determinístico únicamente si `PreparationResult.estado == "correcto"` **y** `MessageAnalysisResult.estado == "correcto"`.

### Contrato `MessageAnalysisResult` y cómo entran los hallazgos sin duplicarse:
El Agente Analizador de Mensajes devuelve siempre un objeto validado (`agents/common/contracts.py`) con:
- `estado`: `"correcto"` | `"incompleto"` | `"error"`
- `categorias_revisadas`, `categorias_sin_hallazgos`, `categorias_no_revisadas` y `estado_categorias` (`"revisada_con_hallazgos"`, `"revisada_sin_hallazgos"`, `"no_revisada"`). Si falta cualquiera de las 5 categorías obligatorias, el contrato prohíbe `estado == "correcto"` y exige `estado == "incompleto"`.
- `senales_encontradas`: Lista de `MessageSignalFinding` con `id_senal`, `categoria_skill`, `categoria_motor`, `severidad`, `descripcion`, `fragmento_justificacion` y `evidence_snippets`.
- **Verificación anti-alucinación en código (`verify_snippets_in_text` y `MessageSignalFinding.validate`):** Cada fragmento devuelto se contrasta literalmente con el texto analizado (`snip in analyzed_text`). Cualquier evidencia inventada o inexistente lanza `ContractValidationError`.
- **Integración sin doble puntuación (`TextAnalyzer.compose_analysis_from_agent_findings`):** Cuando el Orquestador ejecuta `ejecutar_motor_deterministico`, pasa los hallazgos validados del `AnalizadorMensajesAgent` en `precomputed_agent_indicators`. El método `compose_analysis_from_agent_findings` en `scripts/analyzer.py` deduplica por `id_senal`, respeta el orden canónico de reglas, **no vuelve a ejecutar** los 5 detectores delegados y solo complementa las 2 verificaciones transversales (`SEC-PROMPT-INJECTION` y `SUP-SUPLANTACION-ENTIDAD`), preservando exactamente los mismos pesos, bonificaciones de combinación y umbrales de `RiskClassifier`.

---

## 🏗️ 3. Estructura Modular del Proyecto

```text
detective-estafas-digitales/
│
├── README.md                         # Documentación integral, instalación y arquitectura de agentes
├── Dockerfile                        # Contenedor seguro (Motor CLI, App Web, Agentes, OCR y PDF)
├── compose.yaml                      # Orquestación con Docker Compose (puerto 127.0.0.1:8502:8501 y volumen ./output)
├── .env.example                      # Plantilla de variables de entorno (GEMINI_MODEL=gemini-3.5-flash-lite)
├── requirements.txt                  # Dependencias del motor base (pytest - motor en stdlib pura)
├── requirements-web.txt              # Dependencias web y agentes (Streamlit, Pillow, Pytesseract, ReportLab, google-genai)
├── app.py                            # Punto de entrada de la aplicación web (Modo Local + Modo Orquesta IA)
│
├── .agents/                          # Skills del sistema (cargadas por Antigravity y por skill_loader.py)
│   └── skills/
│       ├── detective-estafas-digitales/SKILL.md
│       ├── validar-entrada/SKILL.md
│       ├── extraer-texto-captura/SKILL.md
│       ├── extraer-enlaces/SKILL.md
│       ├── detectar-urgencia/SKILL.md
│       ├── detectar-amenazas/SKILL.md
│       ├── detectar-premios/SKILL.md
│       ├── detectar-pedidos-datos/SKILL.md
│       └── detectar-pedidos-dinero/SKILL.md
│
├── agents/                           # Orquesta de Agentes IA - Etapas 1 y 2
│   ├── common/
│   │   ├── contracts.py              # Contratos (AgentInputRequest, PreparationResult, MessageAnalysisResult, OrchestratorResponse)
│   │   ├── skill_loader.py           # Cargador y validador programático de SKILL.md y permisos por agente
│   │   ├── llm_client.py             # Ciclo real de tool-calling (y parallel tool-calling) con google-genai, límites y timeouts
│   │   ├── privacy.py                # Enmascaramiento preventivo de PII en textos, URLs y respuestas de herramientas
│   │   └── traceability.py           # Registro auditable de eventos y acumulador de llamadas/tokens por agente
│   ├── tools/
│   │   ├── preparation_tools.py      # Herramientas Python de preparación y motor determinístico
│   │   └── message_analysis_tools.py # 5 herramientas Python de detección de señales con verificación literal de evidencia
│   ├── preparador/
│   │   └── agent.py                  # Agente Preparador (PreparadorAgent)
│   ├── analizador_mensajes/
│   │   └── agent.py                  # Agente Analizador de Mensajes (AnalizadorMensajesAgent)
│   └── orquestador/
│       └── agent.py                  # Agente Orquestador (OrquestadorAgent) que coordina el flujo de 3 etapas
│
├── scripts/                          # Motor determinístico funcional (Python 3.10+)
│   ├── worker.py                     # Punto de entrada seguro (CLI / STDIN / Pipeline)
│   ├── analyzer.py                   # Analizador heurístico y compositor de hallazgos de agentes sin duplicación
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
└── tests/                            # Batería de 115 pruebas automatizadas con pytest
    ├── test_agents_orchestration.py  # 31 pruebas de Orquestador, Preparador, Analizador de Mensajes, Skills, equivalencia y seguridad
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
Podés copiar la plantilla `.env.example` a `.env` o definir las variables en tu terminal antes de iniciar la aplicación:

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

### Paso 3: Iniciar la Aplicación Web en Streamlit (Ejecución Local)
```bash
streamlit run app.py --server.port 8502
```
Abrirá la interfaz en `http://localhost:8502`.

---

## 🚀 5. Cómo Probar la Aplicación desde Streamlit (`http://localhost:8502`)

1. **Seleccionar el modo de operación (Barra lateral izquierda):**
   - **🔒 Modo Local Determinístico (Sin Red):** Ejecuta directamente el motor heurístico y el OCR local sin llamadas externas.
   - **🤖 Modo Orquesta de Agentes IA:** Ejecuta el recorrido `Streamlit ➔ Orquestador ➔ Preparador ➔ Analizador de Mensajes (5 skills) ➔ Evaluación determinística`.
2. **Probar en la pestaña "📝 Pegar Texto":**
   - Cargá un ejemplo desde el selector o pegá un mensaje sospechoso y presioná **"🔍 Analizar Mensaje"**.
   - En el **Modo Orquesta de Agentes IA**, además del dictamen de riesgo, podés desplegar el panel **"🧭 Ver Detalle de Orquestación de Agentes IA (Preparación, Análisis de Mensaje, Privacidad y Trazas)"**, que muestra:
     - **Paso 1 — Agente Preparador:** `estado`, `detalle_estado`, enlaces extraídos y herramientas ejecutadas.
     - **Paso 2 — Agente Analizador de Mensajes (Etapa 2):** Estado (`correcto`/`incompleto`/`error`), categorías revisadas (`5/5`), categorías sin hallazgos, y el listado de señales encontradas con su ID estable (`ING-*` / `FRA-*`) y el fragmento literal del texto que la justifica.
     - **Métricas Acumuladas de Consumo IA:** Llamadas totales al LLM, llamadas a herramientas y tokens acumulados (entrada, salida y total) desglosados por agente (`orquestador`, `preparador`, `analizador_mensajes`).
     - **Aviso de Privacidad y Trazabilidad Completa:** Registro paso a paso de cada evento con tiempos en milisegundos.
3. **Probar en la pestaña "📷 Subir Captura (OCR)":**
   - Subí una imagen PNG/JPG/WebP (por ejemplo, `examples/captura_phishing_bancario.png`).
   - Presioná **"🤖 Preparar y Analizar Captura con Agentes IA"** para ejecutar todo el flujo desde la imagen hasta el análisis de las 5 categorías del mensaje extraído, o bien extraé primero el texto para revisarlo manualmente antes de analizarlo.
4. **Descargar o Guardar el Informe:**
   - Al pie de los resultados, usá **"📄 Descargar Informe Completo en PDF"** o **"💾 Guardar Informe en Carpeta Local (output/)"**.

---

## 🐳 5.1. Ejecución con Docker y Docker Compose

El archivo `compose.yaml` levanta el servicio `detective-web` publicando el puerto `127.0.0.1:8502:8501` (`http://localhost:8502` en el anfitrión hacia el puerto `8501` en el que escucha Streamlit dentro del contenedor), corriendo con el usuario sin privilegios `10001:10001`, montando `./output` en `/app/output` y pasando de forma opcional las variables `GEMINI_API_KEY`, `GEMINI_MODEL` y `DETECTIVE_DIAGNOSTICS`.

### 1. Iniciar o actualizar únicamente el servicio del Detective con Docker Compose
```bash
# Construir e iniciar en segundo plano el servicio detective-web:
docker compose up --build -d detective-web

# Verificar el estado y el mapeo de puertos:
docker compose ps
```
Luego abrí **`http://localhost:8502`** en tu navegador.

### 2. Ejecutar las pruebas automatizadas dentro del contenedor Docker
```bash
docker exec -e DETECTIVE_SKIP_DOTENV=1 -e GEMINI_API_KEY= detective-estafas-web pytest -v
```

---

## 🧪 6. Pruebas Automatizadas (115 Tests en Total) y Validación Real

El proyecto cuenta con **115 pruebas automatizadas con `pytest`** distribuidas en 12 archivos de prueba, incluyendo **31 pruebas en `tests/test_agents_orchestration.py`** que cubren las Etapas 1 y 2:

```bash
.venv\Scripts\python.exe -m pytest -v
```

### Escenarios verificados en `tests/test_agents_orchestration.py` (31 tests):
1. **Carga programática y autorización de las 8 skills de agentes:** Verifica `validar-entrada`, `extraer-texto-captura`, `extraer-enlaces` (Preparador) y `detectar-urgencia`, `detectar-amenazas`, `detectar-premios`, `detectar-pedidos-datos`, `detectar-pedidos-dinero` (Analizador de Mensajes), bloqueando accesos cruzados entre agentes y *path traversal* (4 tests).
2. **Cada una de las 5 categorías con y sin hallazgos:** Verifica `urgencia` (`ING-URGENCIA-ARTIFICIAL`), `amenazas` (`ING-AMENAZA-BLOQUEO`), `premios` (`FRA-PREMIO-INESPERADO`), `pedidos_datos` (`FRA-CAPTURA-CREDENCIALES`) y `pedidos_dinero` (`FRA-PAGO-ANTICIPADO` y `FRA-DEBIN-ENGANOSO`), comprobando que las demás categorías queden en `revisada_sin_hallazgos` y que un mensaje benigno deje las 5 en `revisada_sin_hallazgos` (7 tests).
3. **Mensajes con múltiples señales simultáneas:** Verifica la detección combinada de las 5 categorías en un solo turno paralelo de herramientas (1 test).
4. **Ausencia de evidencia inventada:** Verifica que `verify_snippets_in_text` y `MessageSignalFinding.validate` rechacen con `ContractValidationError` cualquier fragmento que no exista literalmente en el texto analizado (1 test).
5. **Categorías omitidas y fallo de herramienta:** Comprueba que si faltan categorías obligatorias el resultado sea `estado="incompleto"` (nunca `correcto`) y el riesgo sea `INDETERMINADO` (nunca `BAJO`), y que el fallo técnico de un detector produzca `estado="error"` (2 tests).
6. **Ausencia de doble puntuación y equivalencia exacta de puntaje:** Verifica en 5 escenarios representativos (phishing bancario, premio falso + pago anticipado, estafa DEBIN, mensaje legítimo e inyección de prompt) que el puntaje (`score`), nivel (`level`), indicadores (`indicators_detected`) y reglas activadas (`activated_rules`) del Modo Orquesta de Agentes coincidan exactamente con los del Modo Local, y demuestra que `compose_analysis_from_agent_findings` utiliza genuinamente los hallazgos del agente sin reejecutar las 5 categorías (6 tests).
7. **Recorrido completo desde texto, captura OCR legible, captura en blanco y Prompt Injection:** Verifica el flujo `Orquestador ➔ Preparador ➔ Analizador de Mensajes ➔ Evaluación` tanto desde texto como desde imagen preparada, y el tratamiento de órdenes maliciosas dentro del mensaje como datos no confiables (4 tests).
8. **Controles de seguridad en código, orden de ejecución, privacidad de URLs/snippets y métricas de consumo:** Verifica el bloqueo de llamadas fuera de orden en el Orquestador, el rechazo de herramientas o argumentos no autorizados en el Analizador de Mensajes, la sanitización de credenciales/PII en URLs (`sanitize_url_for_external_llm`) y fragmentos de herramientas (`sanitize_snippets_for_external_llm`), y el conteo acumulado de llamadas y tokens en `usage_metrics` (4 tests).
9. **Prueba de integración real contra la API de Google Gemini (`test_real_gemini_api_orchestration_when_configured`):** Ejecutada con `gemini-3.5-flash-lite` y datos ficticios (`PASSED`), comprobando la delegación real `Orquestador ➔ Preparador ➔ Analizador de Mensajes (5 skills en paralelo) ➔ Motor Determinístico`, con `9` llamadas totales al modelo, `10` llamadas a herramientas y `24.208` tokens acumulados (`23.453` de entrada + `755` de salida).

### Resumen de Verificación Efectivamente Realizada (Etapa 2):
- **Suite determinística y con cliente LLM simulado (`pytest`):** `114 passed, 1 skipped` ejecutada tanto en el entorno virtual local de Windows (`.venv`) como dentro del contenedor Docker (`docker exec -e DETECTIVE_SKIP_DOTENV=1 -e GEMINI_API_KEY= detective-estafas-web pytest -v`).
- **Integración en vivo con Google Gemini API (`gemini-3.5-flash-lite`):** Verificada mediante `test_real_gemini_api_orchestration_when_configured` (`1 passed`), comprobando en las trazas la delegación real `Orquestador ➔ Preparador ➔ Analizador de Mensajes ➔ Motor Determinístico`, la revisión de las 5 categorías obligatorias y el consumo acumulado (`9` llamadas al modelo, `10` llamadas a herramientas y `24.208` tokens totales).
- **Comprobación manual en la aplicación (`http://localhost:8502`):** Verificada manualmente por el usuario sobre la aplicación en ejecución con la Etapa 2 integrada, confirmando su correcto funcionamiento.

---

## ⚠️ 7. Honestidad Metodológica y Limitaciones

1. **Puntaje Heurístico (0-100):** Refleja la acumulación de indicadores de severidad identificados. **No representa una probabilidad matemática de fraude.**
2. **Ausencia de Señales != Mensaje Legítimo:** Que un mensaje obtenga **Riesgo BAJO (0/100)** indica que no se encontraron patrones conocidos, pero **no constituye un aval absoluto de autenticidad**.
3. **Captura Ilegible o Análisis Incompleto != Riesgo Bajo:** Si una imagen no contiene texto reconocible por OCR o si no se completan las 5 categorías obligatorias del analizador de mensajes, el sistema informa `estado="incompleto"` y asigna riesgo `INDETERMINADO`.
4. **Análisis Estático de Enlaces:** Por seguridad, el sistema nunca visita las URLs sospechosas ni resuelve redirecciones activas en acortadores como `bit.ly`.
5. **Enmascaramiento Heurístico de PII:** El filtro de privacidad enmascara patrones estructurados (CBU/CVU, tarjetas, DNI, CUIT/CUIL, emails, teléfonos y parámetros sensibles en URLs), pero el usuario debe evitar enviar información confidencial no estructurada cuando utilice un proveedor externo de IA.

---

## 🎓 8. Materiales Oficiales para la Defensa Oral

- **Presentación Oficial (PowerPoint):** [Detective_Estafas_Digitales_Presentacion_FINAL.pptx](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/Detective_Estafas_Digitales_Presentacion_FINAL.pptx)
- **Guion de Defensa Oral (PDF):** [Guion_Defensa_Oral_Detective_Estafas_FINAL.pdf](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/Guion_Defensa_Oral_Detective_Estafas_FINAL.pdf)
- **Guion de Defensa Oral (Word):** [Guion_Defensa_Oral_Detective_Estafas_FINAL.docx](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/Guion_Defensa_Oral_Detective_Estafas_FINAL.docx)
- **Manual de la Aplicación Web:** [docs/manual_web.md](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/docs/manual_web.md)
