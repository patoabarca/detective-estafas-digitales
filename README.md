# 🛡️ Detective de Estafas Digitales
## Skill de IA para Antigravity + Orquesta de Agentes IA (Etapas 1, 2, 3 y 4) + Mini Aplicación Web con OCR y Exportador PDF

Trabajo Práctico para la **Diplomatura en Inteligencia Artificial**.

---

## 📋 1. Resumen Ejecutivo y Objetivos

**Detective de Estafas Digitales** es una solución de ciberseguridad explicable diseñada para proteger a los usuarios frente a fraudes digitales cotidianos: **phishing, suplantación de identidad (spoofing), falso premio con pago anticipado, maniobras de DEBIN e ingeniería social**.

El proyecto nació como una Skill para agentes de inteligencia artificial en **Google Antigravity**, fue ampliado con una **mini aplicación web en Streamlit con OCR local** y evoluciona hacia una **Orquesta de Agentes IA (Etapas 1 a 4)** que integra:
- **Agente Orquestador** (`agents/orquestador/`),
- **Agente Preparador** (`agents/preparador/`) con 3 skills de preparación, y
- **Agente Analizador de Mensajes** (`agents/analizador_mensajes/`) con 5 skills especializadas de detección lingüística,
- **Agente Analizador de Enlaces** (`agents/analizador_enlaces/`) con 1 skill de auditoría sintáctica Zero Network, y
- **Agente Evaluador** (`agents/evaluador/`) con 6 skills especializadas (`reunir-hallazgos`, `calcular-puntaje`, `asignar-nivel-riesgo`, `explicar-resultado`, `recomendar-cuidados`, `generar-pdf`),
ejecutándose mediante llamadas reales a herramientas (`tool-calling` y *parallel tool calling*) sobre la API oficial de Google Gemini (`google-genai`, modelo `gemini-3.5-flash-lite`), manteniendo intacto el **Modo Local Determinístico (Sin Red)** y la equivalencia exacta de puntuación.

### Principios Rectores:
1. **Doble Modo en la App Web + Vía CLI:** La aplicación web permite alternar entre el **Modo Local Determinístico (Zero Network)** y el **Modo Orquesta de Agentes IA (Orquestador + Preparador + Analizador de Mensajes + Analizador de Enlaces + Evaluador)**, reutilizando las reglas del motor heurístico, el OCR local y el clasificador de riesgo sin duplicar lógica ni sumar dos veces una misma regla.
2. **Seguridad Ofensiva y Defensiva:** Trata cualquier mensaje ingresado o texto extraído como **información no confiable (Untrusted Data)**. Neutraliza intentos de **Prompt Injection / Jailbreak**, prohíbe la ejecución de comandos o herramientas fuera de la lista blanca de cada agente y verifica en código que todo fragmento de evidencia pertenezca literalmente al texto analizado (rechazo de evidencia inventada).
3. **Cero Visitas a Enlaces Sospechosos:** Tanto en el modo local como en el modo de agentes, el análisis de enlaces y dominios es 100% estático y local. **Nunca visita ni consulta las URLs del mensaje**.
4. **Visión por Computadora y OCR Local:** Procesamiento de capturas de pantalla en memoria RAM con Tesseract OCR local. En el modo de agentes, el Agente Preparador invoca la herramienta local `tool_extraer_texto_captura` sin enviar los bytes crudos de la imagen al proveedor externo.
5. **Revisión Humana Obligatoria (Human-in-the-loop):** Heurística preventiva de anomalías en URLs reconocidas por OCR con advertencias visuales y editor interactivo. Una captura ilegible o un análisis de mensaje con categorías omitidas produce estado `incompleto` y riesgo `INDETERMINADO` — nunca evidencia inventada ni riesgo `BAJO`.
6. **Clasificación Explicable (Sin Cajas Negras):** La determinación del nivel de riesgo se realiza mediante reglas ponderadas y documentadas (`config/policy.json`). Las puntuaciones representan una **escala heurística de severidad acumulada (0-100)** y **NO una probabilidad estadística**.
7. **Informes Descargables en PDF y Persistencia Local/Docker:** Exportación formal de informes generados en memoria con ReportLab para descarga por navegador o guardado en `output/`.

---

## 🏛️ 2. Arquitectura General: Modos de Ejecución y Orquesta de Agentes (Etapas 1, 2, 3 y 4)

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
│  VÍA 2B: APP WEB STREAMLIT - MODO ORQUESTA DE AGENTES (ETAPAS 1 A 4)   │
│                                                                        │
│   Streamlit (app.py)                                                   │
│     ➔ Sanitización preventiva de PII en texto, URLs y snippets         │
│     ➔ Agente Orquestador (agents/orquestador/ - Gemini Tool-Calling)   │
│         ├── 1. Tool: delegar_preparacion                               │
│         │     ➔ Agente Preparador (agents/preparador/)                 │
│         │         ├── Skill + Tool: validar-entrada                    │
│         │         ├── Skill + Tool: extraer-texto-captura (si imagen)  │
│         │         └── Skill + Tool: extraer-enlaces (solo extracción)  │
│         │     ➔ PreparationResult (estado, detalle_estado, url_ids)    │
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
│         ├── 3. Tool: delegar_analisis_enlaces (condicional si hay URLs)│
│         │     ➔ Agente Analizador de Enlaces                           │
│         │       (agents/analizador_enlaces/ - Batch Tool-Calling)      │
│         │         └── Skill + Tool: analizar-url                       │
│         │     ➔ UrlAnalysisResult (REGLA-URL-01 a 05, Zero Network,    │
│         │       advertencias o motivo_omision si sin_enlaces)          │
│         └── 4. Tool: delegar_evaluacion (si todo OK)                   │
│               ➔ Agente Evaluador (agents/evaluador/)                   │
│                   ├── Skill + Tool: reunir-hallazgos                   │
│                   ├── Skill + Tool: calcular-puntaje                   │
│                   ├── Skill + Tool: asignar-nivel-riesgo               │
│                   ├── Skill + Tool: explicar-resultado                 │
│                   ├── Skill + Tool: recomendar-cuidados                │
│                   └── Skill + Tool: generar-pdf (si se solicita)       │
│               ➔ EvaluationResult (score, level, rules, recommendations)│
│     ➔ OrchestratorResponse + Trazabilidad + Métricas + Informe PDF     │
└────────────────────────────────────────────────────────────────────────┘
```

### Diferencia entre el Modo Local y el Modo con Agentes IA:
| Característica | Modo Local Determinístico | Modo Orquesta de Agentes IA (Etapas 1, 2, 3 y 4) |
| :--- | :--- | :--- |
| **Conexión de red** | **Cero (100% Offline / Zero Network)**. No realiza ninguna petición externa. | **Habilitada hacia el proveedor IA configurado** (`google-genai` / Gemini API). **Nunca visita las URLs sospechosas del mensaje.** |
| **Requisitos de credenciales** | Ninguno. Funciona sin `.env` ni claves. | Requiere `GEMINI_API_KEY` (y `GEMINI_MODEL=gemini-3.5-flash-lite`). |
| **Ejecución de OCR, URLs, Detección y Evaluación** | Local en memoria RAM (`scripts/analyzer.py`, `scripts/url_analyzer.py`, `scripts/risk_classifier.py`, `web/ocr_service.py`). | Orquestada mediante herramientas autorizadas por el **Agente Preparador** (3 skills), el **Agente Analizador de Mensajes** (5 skills), el **Agente Analizador de Enlaces** (1 skill) y el **Agente Evaluador** (6 skills). |
| **Integración en la evaluación sin doble puntuación** | Ejecuta directamente `TextAnalyzer.analyze()` y `RiskClassifier.classify()`. | `EvaluadorAgent` reúne hallazgos deduplicados de ambos analistas, preserva la procedencia de URLs y aplica en Python puro `calculate_score` y `assign_risk_level` con idénticas ponderaciones y umbrales. |
| **Privacidad de datos** | El texto jamás sale de la máquina local o contenedor. | Se aplica **enmascaramiento preventivo de PII** (`agents/common/privacy.py`) al texto enviado al LLM, a los parámetros sensibles de URLs y a las respuestas de herramientas que vuelven al modelo, conservando el original en memoria local. |
| **Fallo de API, categorías omitidas o falta de clave** | No aplica. | Si falta clave o falla una herramienta reporta `estado="error"`. Si faltan categorías obligatorias sin revisar reporta `estado="incompleto"` y riesgo `INDETERMINADO` (nunca `correcto` ni `BAJO`). |

---

## 🧩 2.1. Skills y Herramientas de la Orquesta (Etapas 1, 2, 3 y 4)

El repositorio cuenta con **16 Skills** en `.agents/skills/`, cuyas instrucciones y metadatos YAML son cargados y validados programáticamente en tiempo de ejecución por `agents/common/skill_loader.py`:

| Skill (`.agents/skills/<nombre>/SKILL.md`) | Agente Autorizado | Herramienta Python Asociada | Regla / Señal Asociada (`policy.json`) | Responsabilidad Única |
| :--- | :--- | :--- | :--- | :--- |
| `validar-entrada` | `preparador` | `tool_validar_entrada` | — | Validar tipo de entrada (`text` o `ocr_screenshot`), longitud, formato binario (PNG/JPEG/WebP), tamaño (≤10 MB) y dimensiones (≤25 MP). |
| `extraer-texto-captura` | `preparador` | `tool_extraer_texto_captura` | — | Preprocesar la captura y extraer texto con Tesseract OCR local + detectar distorsiones en URLs. |
| `extraer-enlaces` | `preparador` | `tool_extraer_enlaces` | — | Extraer URLs candidatas en el texto y asignar identificadores de sesión (`URL-1`, ...) sin visitar la red ni evaluar riesgo. |
| `detectar-urgencia` | `analizador_mensajes` | `tool_detectar_urgencia` | `ING-URGENCIA-ARTIFICIAL` (`+15 pts`) | Detectar presión temporal, plazos perentorios o apuro deliberado (`_detect_urgency`). |
| `detectar-amenazas` | `analizador_mensajes` | `tool_detectar_amenazas` | `ING-AMENAZA-BLOQUEO` (`+35 pts`) | Detectar amenazas de bloqueo, suspensión, cierre de cuenta o embargo (`_detect_blocking_threats`). |
| `detectar-premios` | `analizador_mensajes` | `tool_detectar_premios` | `FRA-PREMIO-INESPERADO` (`+25 pts`) | Detectar sorteos falsos, premios inesperados o beneficios señuelo (`_detect_fake_rewards`). |
| `detectar-pedidos-datos` | `analizador_mensajes` | `tool_detectar_pedidos_datos` | `FRA-CAPTURA-CREDENCIALES` (`+40 pts`) | Detectar solicitudes de claves, contraseñas, tokens, códigos OTP/SMS o validación de identidad (`_detect_credential_harvesting`). |
| `detectar-pedidos-dinero` | `analizador_mensajes` | `tool_detectar_pedidos_dinero` | `FRA-PAGO-ANTICIPADO` (`+35 pts`) y `FRA-DEBIN-ENGANOSO` (`+30 pts`) | Detectar pedidos de pagos previos para liberar paquetes/premios (`_detect_advance_fee`) y maniobras de DEBIN o transferencias por error (`_detect_debin_trick`). |
| `analizar-url` | `analizador_enlaces` | `tool_analizar_url` | `REGLA-URL-01` a `REGLA-URL-05` (`+20` a `+30 pts`) | Auditar estáticamente la estructura sintáctica de las URLs extraídas (IP numérica, subdominios engañosos, Punycode/homóglifos, credenciales embebidas, TLD de bajo costo) con política Zero Network. |
| `reunir-hallazgos` | `evaluador` | `tool_reunir_hallazgos` | — | Unificar y deduplicar hallazgos validados de ambos analistas conservando evidencia y procedencia de URLs. |
| `calcular-puntaje` | `evaluador` | `tool_calcular_puntaje` | Todas las reglas del motor | Ejecutar en Python las reglas existentes sobre los hallazgos reunidos sin que el modelo invente ni altere puntos. |
| `asignar-nivel-riesgo` | `evaluador` | `tool_asignar_nivel_riesgo` | Umbrales de severidad | Asignar en Python el nivel (BAJO, MEDIO, ALTO, INDETERMINADO) sin convertir fallos en riesgo bajo. |
| `explicar-resultado` | `evaluador` | `tool_explicar_resultado` | — | Generar explicación accesible basada estrictamente en hallazgos comprobados sin inventar hechos ni visitas a sitios. |
| `recomendar-cuidados` | `evaluador` | `tool_recomendar_cuidados` | — | Seleccionar recomendaciones preventivas del sistema según riesgo y enlaces sin inventar instituciones. |
| `generar-pdf` | `evaluador` | `tool_generar_pdf` | — | Generar informe descargable en PDF en memoria (ReportLab) a partir de la evaluación final validada. |
| `detective-estafas-digitales` | Agente IDE Antigravity | `scripts/worker.py` (CLI / STDIN) | Todas las reglas del motor | Manifiesto integral para el análisis directo desde el chat de Antigravity IDE. |

Además, el **Agente Orquestador** (`orquestador`) tiene una lista cerrada de **4 herramientas** registradas en `agents/orquestador/agent.py`, cuyo orden obligatorio se hace cumplir en código Python:
1. `delegar_preparacion`: Invoca al `PreparadorAgent` y devuelve `PreparationResult`.
2. `delegar_analisis_mensaje`: Invoca al `AnalizadorMensajesAgent` únicamente si `PreparationResult.estado == "correcto"` y devuelve `MessageAnalysisResult`.
3. `delegar_analisis_enlaces`: Invoca al `AnalizadorEnlacesAgent` condicionalmente si se extrajeron enlaces en la preparación (`len(enlaces_encontrados) > 0`). Si no hay enlaces, omite la llamada registrando el motivo (`sin_enlaces`) sin tratarlo como error.
4. `delegar_evaluacion`: Invoca al `EvaluadorAgent` pasando los hallazgos validados de ambos analistas y advertencias del preparador para ejecutar secuencialmente las 6 skills de evaluación y devolver `EvaluationResult`.

### Contrato `UrlAnalysisResult` y evaluación de enlaces:
El Agente Analizador de Enlaces devuelve siempre un objeto validado (`agents/common/contracts.py`) con:
- `estado`: `"correcto"` | `"incompleto"` | `"error"`
- `detalle_estado`: `"sin_enlaces"` | `"analizados_sin_senales"` | `"analizados_con_senales"` | `"direccion_no_analizable"` | `"enlaces_omitidos"` | `"fallo_herramienta"`
- `intervino_agente`: Booleano que distingue si el agente analizó enlaces o si se omitió por ausencia de enlaces en el mensaje.
- `enlaces_analizados`: Lista de `UrlItemAnalysisResult` (`url_id`, `raw_url`, `masked_url`, `estado_enlace`, `domain`, `reglas_activadas`, `senales_encontradas`, `advertencias`, `ocr_warnings`).
- **Garantías anti-alucinación y seguridad:** Prohíbe declarar `estado == "correcto"` si se omitieron enlaces extraídos o si alguna dirección no pudo analizarse. Advierte explícitamente que la ausencia de señales sintácticas NO garantiza que un sitio sea seguro. No autocorrige enlaces dudosos extraídos por OCR.

### Contrato `MessageAnalysisResult` y cómo entran los hallazgos sin duplicarse:
El Agente Analizador de Mensajes devuelve siempre un objeto validado (`agents/common/contracts.py`) con:
- `estado`: `"correcto"` | `"incompleto"` | `"error"`
- `categorias_revisadas`, `categorias_sin_hallazgos`, `categorias_no_revisadas` y `estado_categorias` (`"revisada_con_hallazgos"`, `"revisada_sin_hallazgos"`, `"no_revisada"`). Si falta cualquiera de las 5 categorías obligatorias, el contrato prohíbe `estado == "correcto"` y exige `estado == "incompleto"`.
- `senales_encontradas`: Lista de `MessageSignalFinding` con `id_senal`, `categoria_skill`, `categoria_motor`, `severidad`, `descripcion`, `fragmento_justificacion` y `evidence_snippets`.
- **Verificación anti-alucinación en código (`verify_snippets_in_text` y `MessageSignalFinding.validate`):** Cada fragmento devuelto se contrasta literalmente con el texto analizado (`snip in analyzed_text`). Cualquier evidencia inventada o inexistente lanza `ContractValidationError`.
- **Integración sin doble puntuación (`TextAnalyzer.compose_analysis_from_agent_findings`):** Cuando el Orquestador ejecuta `ejecutar_motor_deterministico` o delega al `EvaluadorAgent`, pasa los hallazgos validados del `AnalizadorMensajesAgent` en `precomputed_agent_indicators`. El método `compose_analysis_from_agent_findings` en `scripts/analyzer.py` deduplica por `id_senal`, respeta el orden canónico de reglas, **no vuelve a ejecutar** los 5 detectores delegados y solo complementa las 2 verificaciones transversales (`SEC-PROMPT-INJECTION` y `SUP-SUPLANTACION-ENTIDAD`), preservando exactamente los mismos pesos, bonificaciones de combinación y umbrales de `RiskClassifier`.

### Contrato `EvaluationResult` y garantías de evaluación (Etapa 4):
El Agente Evaluador devuelve siempre un objeto validado (`agents/common/contracts.py`) con:
- `estado`: `"correcto"` | `"incompleto"` | `"error"`
- `nivel_riesgo`: `"BAJO"` | `"MEDIO"` | `"ALTO"` | `"INDETERMINADO"`
- `puntaje_heuristico`: Entero entre 0 y 100 calculado estrictamente por el motor Python (`scripts/risk_classifier.py`). El modelo LLM no calcula, altera ni inventa puntuaciones.
- `reglas_activadas`: Lista de códigos de regla activados con su procedencia intacta. Al deduplicar hallazgos de URLs, se conserva la evidencia y origen de cada enlace sin alterar la puntuación.
- `explicacion`: Explicación empática y accesible sin tecnicismos innecesarios, basada únicamente en hallazgos comprobados y sin afirmar visitas a sitios externos.
- `recomendaciones`: Selección de "recomendaciones preventivas del sistema" apropiadas al nivel de riesgo y hallazgos específicos, sin inventar teléfonos ni entidades no mencionadas.
- `pdf_generado`: Booleano que indica si se exportó el informe en memoria con ReportLab a partir de la evaluación final validada.
- **Salvaguardas de completitud:** Si la preparación o el análisis de mensajes arrojó estado `incompleto` o `error`, el evaluador asigna forzosamente nivel `INDETERMINADO` (nunca convierte fallos en riesgo bajo).

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
│       ├── detectar-pedidos-dinero/SKILL.md
│       ├── analizar-url/SKILL.md
│       ├── reunir-hallazgos/SKILL.md
│       ├── calcular-puntaje/SKILL.md
│       ├── asignar-nivel-riesgo/SKILL.md
│       ├── explicar-resultado/SKILL.md
│       ├── recomendar-cuidados/SKILL.md
│       └── generar-pdf/SKILL.md
│
├── agents/                           # Orquesta de Agentes IA - Etapas 1 a 4
│   ├── common/
│   │   ├── contracts.py              # Contratos (AgentInputRequest, PreparationResult, MessageAnalysisResult, UrlAnalysisResult, EvaluationResult, OrchestratorResponse)
│   │   ├── skill_loader.py           # Cargador y validador programático de SKILL.md y permisos por agente
│   │   ├── llm_client.py             # Ciclo real de tool-calling (y parallel tool-calling) con google-genai, límites y timeouts
│   │   ├── privacy.py                # Enmascaramiento preventivo de PII en textos, URLs y respuestas de herramientas
│   │   └── traceability.py           # Registro auditable de eventos y acumulador de llamadas/tokens por agente
│   ├── tools/
│   │   ├── preparation_tools.py      # Herramientas Python de preparación
│   │   ├── url_tools.py              # Herramienta Python de auditoría sintáctica de URLs en lote (Zero Network)
│   │   └── evaluation_tools.py       # 6 herramientas Python de evaluación (reunir, calcular, clasificar, explicar, recomendar, pdf)
│   │   └── message_analysis_tools.py # 5 herramientas Python de detección de señales con verificación literal de evidencia
│   ├── preparador/
│   │   └── agent.py                  # Agente Preparador (PreparadorAgent)
│   ├── analizador_mensajes/
│   ├── analizador_enlaces/
│   │   └── agent.py                  # Agente Analizador de Enlaces (AnalizadorEnlacesAgent)
│   ├── evaluador/
│   │   └── agent.py                  # Agente Evaluador (EvaluadorAgent) con 6 skills especializadas
│   │   └── agent.py                  # Agente Analizador de Mensajes (AnalizadorMensajesAgent)
│   └── orquestador/
│       └── agent.py                  # Agente Orquestador (OrquestadorAgent) que coordina el flujo de 4 etapas
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
   - **🤖 Modo Orquesta de Agentes IA:** Ejecuta el recorrido `Streamlit ➔ Orquestador ➔ Preparador ➔ Analizador de Mensajes ➔ Analizador de Enlaces ➔ Evaluador (6 skills)`.
2. **Probar en la pestaña "📝 Pegar Texto":**
   - Cargá un ejemplo desde el selector o pegá un mensaje sospechoso y presioná **"🔍 Analizar Mensaje"**.
   - En el **Modo Orquesta de Agentes IA**, además del dictamen de riesgo, podés desplegar el panel **"🧭 Ver Detalle de Orquestación de Agentes IA (Preparación, Análisis de Mensaje, Privacidad y Trazas)"**, que muestra:
     - **Paso 1 — Agente Preparador:** `estado`, `detalle_estado`, enlaces extraídos y herramientas ejecutadas.
     - **Paso 2 — Agente Analizador de Mensajes (Etapas 2, 3 y 4):** Estado (`correcto`/`incompleto`/`error`), categorías revisadas (`5/5`), categorías sin hallazgos, y el listado de señales encontradas con su ID estable (`ING-*` / `FRA-*`) y el fragmento literal del texto que la justifica.
     - **Métricas Acumuladas de Consumo IA:** Llamadas totales al LLM, llamadas a herramientas y tokens acumulados (entrada, salida y total) desglosados por agente (`orquestador`, `preparador`, `analizador_mensajes`, `analizador_enlaces`, `evaluador`).
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
docker exec -e DETECTIVE_SKIP_DOTENV=1 -e GEMINI_API_KEY= detective-estafas-web pytest -v -k "not test_real_gemini_api_orchestration_when_configured"
```
*Verificación en Docker completada:* Se ejecutaron los 143 tests determinísticos y simulados dentro del contenedor en 4.83s (100% pasando, 0 fallos), se confirmó la presencia de los módulos `agents/analizador_enlaces/` y `agents/evaluador/` con sus 6 skills, y la respuesta HTTP 200 OK en `http://127.0.0.1:8502/_stcore/health` sin afectar el servicio aislado HomeLens (puerto 8501).

---

## 🧪 6. Pruebas Automatizadas (144 Tests en Total), Validación Docker y Comprobación Manual

El proyecto cuenta con **144 pruebas automatizadas con `pytest`** distribuidas en 12 archivos de prueba, incluyendo **60 pruebas en `tests/test_agents_orchestration.py`** que cubren las Etapas 1, 2, 3 y 4:

```bash
.venv\Scripts\python.exe -m pytest -v
```

### Escenarios verificados en `tests/test_agents_orchestration.py` (55 tests):
1. **Carga programática y autorización de las 9 skills de agentes:** Verifica `validar-entrada`, `extraer-texto-captura`, `extraer-enlaces` (Preparador); `detectar-urgencia`, `detectar-amenazas`, `detectar-premios`, `detectar-pedidos-datos`, `detectar-pedidos-dinero` (Analizador de Mensajes); y `analizar-url` (Analizador de Enlaces), bloqueando accesos cruzados entre agentes y *path traversal* (5 tests).
2. **Inspección de URLs y reglas existentes (REGLA-URL-01 a REGLA-URL-05):** Verifica detección de IP directa en host, subdominios engañosos/marcas suplantadas, caracteres homóglifos o Punycode, credenciales de usuario embebidas (`userinfo`) y TLDs de bajo costo/alta incidencia, con evidencia concreta (5 tests).
3. **Múltiples URLs y procesamiento en lote:** Verifica que múltiples enlaces se procesen en una sola llamada de herramienta (`batch`), sin duplicar URLs repetidas ni sumar dos veces la puntuación de un mismo enlace (2 tests).
4. **Tratamiento de direcciones dudosas y contratos:** Verifica que URLs dudosas detectadas por OCR conserven sus advertencias originales sin autocorrección inventada, que enlaces malformados marquen estado `incompleto` con riesgo `INDETERMINADO`, que el modelo no pueda inventar ni sustituir URLs en las herramientas, y que intentos de inyección dentro de la ruta o query de la URL se traten como datos pasivos no confiables (5 tests).
5. **Cada una de las 5 categorías de mensaje con y sin hallazgos:** Verifica `urgencia` (`ING-URGENCIA-ARTIFICIAL`), `amenazas` (`ING-AMENAZA-BLOQUEO`), `premios` (`FRA-PREMIO-INESPERADO`), `pedidos_datos` (`FRA-CAPTURA-CREDENCIALES`) y `pedidos_dinero` (`FRA-PAGO-ANTICIPADO` y `FRA-DEBIN-ENGANOSO`), comprobando que las demás categorías queden en `revisada_sin_hallazgos` y que un mensaje benigno deje las 5 en `revisada_sin_hallazgos` (7 tests).
6. **Ausencia de evidencia inventada y estados incompletos:** Verifica que cualquier fragmento de texto o enlace no coincidente literalmente sea rechazado con `ContractValidationError`, y que categorías o enlaces omitidos produzcan estado `incompleto` y riesgo `INDETERMINADO` (nunca `BAJO`) (2 tests).
7. **Ausencia de doble puntuación y equivalencia exacta:** Verifica en 5 escenarios representativos (phishing bancario, premio falso + pago anticipado, estafa DEBIN, mensaje legítimo e inyección de prompt) que el puntaje (`score`), nivel (`level`), indicadores y reglas activadas del Modo Orquesta de Agentes coincidan exactamente con el Modo Local, y demuestra que el motor utiliza genuinamente los hallazgos precalculados sin reejecutar el análisis de URLs (6 tests).
8. **Controles de seguridad en código, privacidad, resiliencia 429 y presupuestos de tiempo:** Verifica el orden estricto de ejecución, el bloqueo de herramientas/argumentos no autorizados, la sanitización de credenciales/tokens en URLs (`path`, `query`, `#fragment`), la cancelación inmediata de reintentos cuando el presupuesto de tiempo es insuficiente (`<= 1.5s`), la detención por agotamiento del presupuesto global, el reintento con espera ante límites temporales 429 cuando el tiempo sugerido cabe en el presupuesto restante, el aborto inmediato ante límites 429 que superan el presupuesto restante y la detección de cuota diaria agotada (`GenerateRequestsPerDay`) sin reintentos ciegos (9 tests).
9. **Recorrido completo desde texto y captura OCR legible:** Flujo end-to-end con imagen y texto (2 tests).
10. **Agente Evaluador y sus 6 skills especializadas (Etapa 4):** Verifica la carga programática y autorización estricta de las 6 skills (`reunir-hallazgos`, `calcular-puntaje`, `asignar-nivel-riesgo`, `explicar-resultado`, `recomendar-cuidados`, `generar-pdf`), la reunión y deduplicación de hallazgos conservando la procedencia y evidencia de URLs, el cálculo determinístico del puntaje en Python sin invención ni modificación por el LLM, la clasificación con umbrales y salvaguarda ante estados incompletos o errores (nunca riesgo bajo), la generación de explicaciones accesibles sin alucinación de visitas a sitios externos, la selección de recomendaciones preventivas del sistema, la generación en memoria de informes PDF con ReportLab sin recalcular, el orden de dependencia estricto aun ante llamadas desordenadas en lote, la reducción a 2 llamadas mediante llamadas paralelas a herramientas y la comprobación de que descargar o guardar el PDF insume cero llamadas al modelo (14 tests).
11. **Prueba opcional de integración real contra Google Gemini API (`test_real_gemini_api_orchestration_when_configured`):** Ejecutada con `gemini-3.5-flash-lite` y datos ficticios (`PASSED` en 24.96s), comprobando en vivo la participación sucesiva de los 5 agentes (`orquestador`, `preparador`, `analizador_mensajes`, `analizador_enlaces`, `evaluador`) y las 6 skills de evaluación, con `18` llamadas LLM, `17` llamadas a herramientas, `74.182` tokens acumulados (`72.680` entrada + `1.502` salida), dictamen final con estado `correcto`, nivel `ALTO`, puntaje `100/100` y 4 reglas activadas.

### Resumen de Verificación Efectivamente Realizada (Etapas 3 y 4):
- **Suite determinística y simulada en entorno local (`pytest`):** `143 passed, 1 deselected` en 6.40s en Windows (`.venv`).
- **Verificación en contenedor Docker (`detective-estafas-web`):** Reconstrucción exitosa vía Docker Compose, `143 passed` en 4.83s sin variables de entorno ni acceso a red, y `HTTP 200 OK` en endpoint de salud `http://127.0.0.1:8502/_stcore/health` (conservando HomeLens intacto en 8501).
- **Comprobación manual del usuario en `http://localhost:8502`:** El usuario verificó manualmente en la aplicación web el funcionamiento integral de la Etapa 4 con el Agente Evaluador y sus 6 skills en ambos modos (Modo Local Determinístico y Modo Orquesta de Agentes IA), constatando el correcto dictamen final, puntaje, explicación no técnica, recomendaciones preventivas del sistema, descarga de informe PDF y visualización de trazas.
- **Auditoría de Llamadas al Modelo: Previstas/Simuladas vs. Medidas en Pruebas Reales:**
  * *Llamadas previstas/simuladas por solicitud (optimizadas):* Se diseñó el flujo para requerir **10 llamadas LLM** (en mensajes de texto sin URLs) o **12 llamadas LLM** (en mensajes con URLs), distribuidas en: Orquestador (4 turnos), Preparador (2 turnos con tools paralelas), Analizador de Mensajes (2 turnos con 5 tools paralelas), Analizador de Enlaces (2 turnos en lote o 0 si no hay enlaces) y Evaluador (2 turnos con 5/6 tools paralelas).
  * *Llamadas medidas en ejecución real previa:* En la prueba real no optimizada de la Etapa 4 se registraron **18 llamadas LLM**, 17 herramientas y 74.182 tokens en 24.96s.
  * *Alcance respecto a errores 429:* La optimización a 10–12 llamadas por solicitud reduce significativamente la probabilidad de saturar el límite de 15 solicitudes por minuto (RPM) del nivel gratuito de la API. Sin embargo, **reducir a 12 llamadas no garantiza la eliminación total de errores 429**: si el usuario realiza consultas consecutivas rápidas, si la ventana móvil de 60 segundos del proveedor aún acumula llamadas de solicitudes previas, o si se agota la cuota diaria (`GenerateRequestsPerDay`), el proveedor continuará respondiendo 429. Por esta razón, el sistema implementa la captura formal del error, la espera controlada del tiempo sugerido si cabe dentro del saldo global restante, el aborto limpio sin reintentos ciegos y la notificación comprensible al usuario recomendando esperar unos segundos o usar el Modo Local Determinístico.
- **Auditoría de Presupuestos de Tiempo y Alcance Real:**
  * *Presupuesto global de solicitud:* 60.0 segundos para toda la orquestación.
  * *Presupuesto por agente delegado:* `min(20.0s, remaining_seconds)`. Ningún agente ni reintento puede iniciarse si el presupuesto restante se agota.
  * *Timeout por petición HTTP:* 30.000 ms (30s) en el cliente `google-genai`.
  * *Reintento transitorio único:* 1 solo reintento ante errores 503/504 con backoff de 1.5s, condicionado a que resten más de 1.5s en el presupuesto (`rem_for_retry > 1.5s`). Si el saldo es menor, el reintento se aborta sin esperar.
  * *Alcance real del límite de 60 segundos:* Las comprobaciones de tiempo son cooperativas y se evalúan antes de despachar cada agente, llamada y reintento. Sin embargo, las llamadas de red del SDK oficial `google-genai` utilizan sockets bloqueantes síncronos; por lo tanto, el sistema no puede interrumpir de forma preventiva un socket en vuelo a mitad de transferencia física. El límite de 60s garantiza que no se inicien nuevas operaciones al agotarlo, pero no constituye una garantía estricta de tiempo real preemptivo sobre sockets en curso.
- **Detalle de la Primera Prueba Real y Consumo de Tokens:**
  * *Fallo inicial:* La primera prueba real arrojó `504 DEADLINE_EXCEEDED` debido a un timeout de socket muy restrictivo (15s). Se corrigió ampliando el socket timeout a 30s, fijando el presupuesto global en 60s e incorporando el reintento transitorio de 1 disparo.
  * *Consumo registrado:* Las 12 llamadas al modelo y 32.368 tokens corresponden exclusivamente a la ejecución exitosa. En el intento inicial fallido la API interrumpió la conexión por deadline sin devolver metadatos de uso, por lo que su consumo exacto de tokens no fue registrado por el proveedor (se desconoce / no facturado).
- **Detalle de la Prueba Real Autorizada con Google Gemini API (Etapa 4):**
  * *Consumo registrado:* 18 llamadas al modelo, 17 llamadas a herramientas y 74.182 tokens acumulados (72.680 entrada + 1.502 salida) en 24.96 segundos, logrando un dictamen final con estado correcto, nivel ALTO, puntaje 100/100 y 4 reglas activadas. La traza confirmó la ejecución sucesiva y coordinada de los 5 agentes: Orquestador (5 llamadas) ➔ Preparador (3 llamadas) ➔ Analizador de Mensajes (2 llamadas) ➔ Analizador de Enlaces (2 llamadas) ➔ Evaluador (6 llamadas).
  * *Manejo de cuota transitoria:* Se incorporó la captura de errores `429 RESOURCE_EXHAUSTED` dentro de los reintentos transitorios de `agents/common/llm_client.py` para tolerar fluctuaciones de cuota por minuto (RPM) del nivel gratuito sin abortar la ejecución cuando resta tiempo presupuestado.

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
