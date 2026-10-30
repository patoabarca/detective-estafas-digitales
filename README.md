# 🛡️ Detective de Estafas Digitales
## Skill de IA para Antigravity + Mini Aplicación Web con OCR y Exportador PDF

Trabajo Práctico para la **Diplomatura en Inteligencia Artificial**.

---

## 📋 1. Resumen Ejecutivo y Objetivos

**Detective de Estafas Digitales** es una solución de ciberseguridad explicable diseñada para proteger a los usuarios frente a fraudes digitales cotidianos: **phishing, suplantación de identidad (spoofing), falso premio con pago anticipado, maniobras de DEBIN e ingeniería social**.

El proyecto nació como una Skill para agentes de inteligencia artificial en **Google Antigravity** y ha sido **ampliado integralmente con una mini aplicación web en Streamlit con OCR local**, permitiendo que cualquier persona pueda analizar un mensaje sospechoso mediante texto o captura de pantalla sin necesidad de conocimientos de programación ni uso de terminales.

### Principios Rectores:
1. **Doble Vía, Un Mismo Motor:** Una vía agéntica para el LLM y una vía web gráfica para usuarios directos, ambas reutilizando el mismo motor determinístico en Python sin duplicar lógica.
2. **Seguridad Ofensiva y Defensiva:** Trata cualquier mensaje ingresado como **información no confiable (Untrusted Data)**. Neutraliza de forma nativa intentos de **Prompt Injection / Jailbreak** y prohíbe la ejecución de comandos embebidos.
3. **Cero Conexiones de Red en el Motor (Zero Network):** El análisis de enlaces y dominios es 100% estático y local. **Nunca visita ni consulta URLs** (evitando ataques de tracking, Webhooks maliciosos o interacción con servidores atacantes).
4. **Visión por Computadora y OCR Local:** Procesamiento de capturas de pantalla 100% en memoria RAM con Tesseract OCR local. No se envían imágenes a APIs en la nube.
5. **Revisión Humana Obligatoria (Human-in-the-loop):** Heurística preventiva de anomalías en URLs reconocidas por OCR (como confusión de '1' por 'l' o '0' por 'o') con advertencias visuales y editor interactivo.
6. **Clasificación Explicable (Sin Cajas Negras):** La determinación del nivel de riesgo se realiza mediante reglas ponderadas y documentadas (`config/policy.json`). Las puntuaciones representan una **escala heurística de severidad acumulada (0-100)** y **NO una probabilidad estadística**.
7. **Informes Descargables en PDF:** Exportación formal de informes generados en memoria con ReportLab sin persistencia en disco.

---

## 🏛️ 2. Arquitectura General: Dos Vías, Un Mismo Motor

El sistema implementa dos canales de interacción independientes con una estricta separación de responsabilidades:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   VÍA 1: AGENTE DE IA + SKILL                          │
│                                                                        │
│   Usuario ➔ Antigravity (LLM) ➔ SKILL.md ➔ scripts/worker.py (STDIN)    │
│   ➔ Motor Python ➔ JSON estructurado ➔ LLM ➔ Explicación Empática      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                         Comparte el mismo motor
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                  VÍA 2: MINI APLICACIÓN WEB                            │
│                                                                        │
│   Usuario ➔ Streamlit (app.py) ➔ Texto / OCR (Tesseract local)         │
│   ➔ web/analysis_adapter.py ➔ Motor Python ➔ Informe Visual / PDF      │
└────────────────────────────────────────────────────────────────────────┘
```

- **Vía 1 (Agente Antigravity + Skill):** Demuestra el patrón de diseño agéntico de la Diplomatura. El LLM comprende la intención del usuario a partir de consultas naturales, descubre la Skill mediante `SKILL.md`, invoca `scripts/worker.py` por STDIN y sintetiza las evidencias en una respuesta empática.
- **Vía 2 (Mini Web Streamlit + OCR):** Demuestra la accesibilidad social de la herramienta. Ofrece dos modalidades (pegar texto o subir captura con OCR local), auditoría de URLs en texto plano, advertencias tipográficas y descarga de informes PDF en memoria.
- **El Motor Central (`scripts/`):** Aporta determinismo, auditabilidad y seguridad. Extrae evidencias sin alucinar, sin dependencias externas en producción y tratando el texto estrictamente como datos pasivos.

> [!NOTE]
> **Honestidad Técnica:** La aplicación web **NO** afirma utilizar el LLM de Antigravity ni modelos en la nube. Opera de forma 100% determinística y local. El OCR utiliza un modelo preentrenado estándar de código abierto (Tesseract); no se entrenó una red neuronal propia.

---

## 🏗️ 3. Estructura Modular del Proyecto

```text
detective-estafas-digitales/
│
├── README.md                         # Documentación integral, instalación y guía de defensa oral
├── Dockerfile                        # Contenedor seguro para ejecución aislada (Zero Network)
├── .dockerignore                     # Exclusiones de contexto para construcción limpia
├── requirements.txt                  # Dependencias del motor base (pytest - motor en stdlib pura)
├── requirements-web.txt              # Dependencias de la app web (Streamlit, Pillow, Pytesseract, ReportLab)
├── app.py                            # Punto de entrada de la mini aplicación web interactiva (Streamlit)
│
├── .agents/                          # Integración con el sistema de descubrimiento de Skills
│   └── skills/
│       └── detective-estafas-digitales/
│           └── SKILL.md              # Manifiesto accesible para Antigravity IDE
│
├── scripts/                          # Motor determinístico funcional (Python 3.10+)
│   ├── worker.py                     # Orquestador y punto de entrada seguro (CLI / STDIN / Pipeline)
│   ├── analyzer.py                   # Analizador heurístico de patrones e inyecciones de prompt
│   ├── url_analyzer.py               # Extracción y auditoría estática de URLs (IP, Punycode, Subdominios)
│   ├── risk_classifier.py            # Motor de clasificación de riesgo explicable (BAJO/MEDIO/ALTO/INDET)
│   └── report_generator.py           # Generador de reportes en JSON estructurado y Markdown
│
├── web/                              # Capa de presentación y servicios web seguros
│   ├── __init__.py                   # Exportaciones principales del paquete web
│   ├── analysis_adapter.py           # Adaptador seguro entre Streamlit y scripts/ (sin llamadas a shell)
│   ├── image_processor.py            # Validación en memoria (anti Decompression Bombs) y preprocesamiento
│   ├── ocr_service.py                # Servicio local de Tesseract OCR y detección de distorsiones en URLs
│   ├── pdf_exporter.py               # Generación en memoria (BytesIO) de informes PDF con ReportLab
│   └── ui_helpers.py                 # Estilos CSS sobrios, tarjetas de riesgo contrastadas y componentes UI
│
├── docs/                             # Documentación de usuario y capturas del sistema
│   ├── manual_web.md                 # Manual detallado de la aplicación web y configuración de OCR
│   └── capturas/
│       └── app_screenshot.png        # Captura real de la aplicación web en funcionamiento
│
├── references/                       # Base de conocimiento documental para el agente
│   ├── fraud-signals.md              # Catálogo de señales de fraude y modismos argentinos
│   ├── phishing-guide.md             # Fundamentos teóricos de ingeniería social y smishing
│   ├── security-guidelines.md        # Directrices de contención, sandboxing y privacidad
│   └── examples.md                   # Casos de estudio y respuestas de referencia
│
├── config/                           # Parámetros y contratos de datos
│   ├── policy.json                   # Políticas de ejecución, límites de tamaño y ponderaciones
│   └── result_schema.json            # Esquema JSON Schema del reporte final
│
├── tests/                            # Batería de 67 pruebas automatizadas con pytest (100% aprobadas)
│   ├── conftest.py                   # Configuración de rutas e importaciones de pruebas
│   ├── test_agent_skill_integration.py # Pruebas del manifiesto SKILL.md y flujo agéntico (2 tests)
│   ├── test_cli_and_stdin.py         # Pruebas de entrada por STDIN, comillas y errores CLI (7 tests)
│   ├── test_analyzer.py              # Pruebas unitarias de reglas textuales y ambigüedad (7 tests)
│   ├── test_urls.py                  # Pruebas de extracción y anomalías en URLs (8 tests)
│   ├── test_security.py              # Pruebas de Path Traversal, secrets y prompt injection (6 tests)
│   ├── test_integration.py           # Pruebas end-to-end de los escenarios oficiales (6 tests)
│   ├── test_web_adapter.py           # Pruebas de integración del adaptador web en memoria (7 tests)
│   ├── test_ocr.py                   # Pruebas de OCR, detección de anomalías en URLs y saneamiento (10 tests)
│   ├── test_pdf_export.py            # Pruebas de exportación en memoria de PDF con caracteres en español (4 tests)
│   └── test_web_security.py          # Pruebas de validación binaria de imágenes y límites de DoS (10 tests)
│
├── examples/                         # Corpus de pruebas, textos y capturas sintéticas
│   ├── phishing_bancario.txt         # Phishing bancario con amenaza y URL engañosa
│   ├── promocion_falsa.txt           # Sorteo falso y pago anticipado por seguro postal
│   ├── mensaje_legitimo.txt          # Mensaje cotidiano seguro
│   ├── prompt_injection.txt          # Intento de secuestro de agente y robo de claves
│   ├── captura_phishing_bancario.png # Captura sintética de WhatsApp de alerta bancaria
│   ├── captura_promocion_falsa.png   # Captura sintética de sorteo con pago anticipado
│   └── captura_mensaje_legitimo.png  # Captura sintética de recordatorio de turno médico
│
├── Detective_Estafas_Digitales_Presentacion_FINAL.pptx # Presentación PowerPoint oficial (14 diapositivas)
├── Guion_Defensa_Oral_Detective_Estafas_FINAL.pdf      # Guion de defensa oral sincronizado en PDF
└── Guion_Defensa_Oral_Detective_Estafas_FINAL.docx     # Guion de defensa oral sincronizado en Word
```

---

## ⚙️ 4. Instalación y Puesta en Marcha

### Paso 1: Clonar o posicionarse en el proyecto
```bash
cd "detective-estafas-digitales"
```

### Paso 2: Crear y activar el entorno virtual
- **En Windows:**
  ```powershell
  python -m venv .venv
  .venv\Scripts\activate
  ```
- **En Linux / macOS:**
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  ```

### Paso 3: Instalar dependencias
- **Para la aplicación web completa con OCR y PDF:**
  ```bash
  pip install -r requirements-web.txt
  ```
- *(Opcional)* Si solo se desea probar el motor en consola sin interfaz gráfica:
  ```bash
  pip install -r requirements.txt
  ```

### Paso 4: Configurar Tesseract OCR (Para análisis de capturas)
- **En Windows:** Ejecutar en PowerShell `winget install UB-Mannheim.TesseractOCR` asegurándose de marcar **Spanish language data**.
- Si Tesseract no estuviera instalado, la aplicación entra automáticamente en **Modo Asistido**, permitiendo previsualizar la captura y escribir o pegar el texto manualmente.

### Paso 5: Iniciar la Mini Aplicación Web
```bash
streamlit run app.py
```
Abrirá automáticamente la interfaz en `http://localhost:8501`.

---

## 🚀 5. Modos de Uso del Motor

### Opción A: Interfaz Web Streamlit
1. **Modalidad Texto:** Pegar el mensaje en la pestaña *"Pegar Texto"* y presionar *"Analizar Mensaje"*.
2. **Modalidad Captura:** Subir una imagen en *"Subir Captura"*, presionar *"Extraer Texto"*, revisar posibles advertencias de OCR en enlaces web, corregir en el editor interactivo y presionar *"Analizar Texto"*.
3. **Descarga de Informe:** Al pie de los resultados, hacer clic en *"Descargar Informe Completo en PDF"*.

### Opción B: Terminal y Motor Directo (scripts/worker.py)
```bash
# Analizar archivo de ejemplo:
python scripts/worker.py --file examples/phishing_bancario.txt

# Analizar texto directo:
python scripts/worker.py --text "Urgente: Banco Santander bloqueará su tarjeta. Valide en http://192.168.1.5/login"

# Analizar vía STDIN (sin fallos de comillas):
cat examples/promocion_falsa.txt | python scripts/worker.py --stdin

# Salida estructurada en JSON formal:
python scripts/worker.py --file examples/phishing_bancario.txt --json
```

### Opción C: Vía Agente en Google Antigravity
En el chat de Antigravity, consultar en lenguaje natural:
> *"Recibí un WhatsApp que dice que me van a bloquear la cuenta y me pide el token en un link. ¿Es seguro o es una estafa?"*
El agente descubrirá `SKILL.md`, canalizará el mensaje al motor y responderá con recomendaciones empáticas.

---

## 🐳 5.1. Ejecución en Docker (Motor CLI, App Web con OCR y Exportación PDF)

El proyecto cuenta con un `Dockerfile` integral que empaqueta tanto el **motor determinístico CLI** (`scripts/worker.py`) como la **mini aplicación web en Streamlit** (`app.py`), incluyendo **Tesseract OCR** con idioma español (`spa` + `eng`) y el exportador de informes **PDF** (`ReportLab`), corriendo bajo un usuario sin privilegios (`auditor`, UID `10001`).

### Qué se ejecuta dentro de Docker y qué queda afuera:
- **Dentro del contenedor Docker:**
  - El motor determinístico de análisis estático (`scripts/worker.py` y módulos en `scripts/`).
  - La aplicación web interactiva en Streamlit (`app.py` y paquete `web/`).
  - El reconocimiento óptico de caracteres local (**Tesseract OCR**) para capturas de pantalla.
  - La generación de informes descargables en **PDF, JSON y Markdown**.
  - La suite completa de **84 pruebas automatizadas** con `pytest`.
- **Fuera del contenedor Docker (en el sistema anfitrión):**
  - **Google Antigravity IDE / Agente LLM (Vía 1):** El agente de IA reside en el entorno anfitrión, descubre la Skill mediante `.agents/skills/detective-estafas-digitales/SKILL.md` y puede invocar el motor localmente o enviando el mensaje por `STDIN` al contenedor Docker (`docker run --rm --network none -i detective-estafas-digitales --stdin --json`).

### 1. Construir la imagen Docker
Desde la raíz del proyecto, ejecutar:
```bash
docker build -t detective-estafas-digitales .
```

### 2. Ejecutar la aplicación web interactiva (Streamlit + OCR + PDF)
```bash
docker run --rm -p 8501:8501 --entrypoint streamlit detective-estafas-digitales run app.py
```
- Abrir en el navegador de la computadora anfitriona: `http://localhost:8501`.
- Desde allí se puede pegar texto, subir capturas de pantalla para análisis con OCR y **descargar directamente el informe PDF** al equipo anfitrión mediante el botón *"📄 Descargar Informe Completo en PDF"*.

### 3. Probar un análisis desde la terminal (Motor CLI aislado con `--network none`)
```bash
# Analizar un mensaje ficticio pasando texto directo:
docker run --rm --network none detective-estafas-digitales --text "Estimado cliente de Banco Galicia: Su cuenta sera bloqueada hoy. Ingrese su token en https://galicia-validacion.seguridad-bancaria.online/login"

# Analizar un archivo de ejemplo incluido:
docker run --rm --network none detective-estafas-digitales --file examples/phishing_bancario.txt

# Analizar vía STDIN con salida en JSON:
echo "Urgente: valide su clave en http://192.168.1.5/login" | docker run --rm --network none -i detective-estafas-digitales --stdin --json
```

### 4. Recuperar los informes generados (PDF, JSON y Markdown) en la computadora anfitriona
Además de la descarga directa desde el navegador en la interfaz web, el motor CLI permite exportar los tres formatos de informe (`informe_detective.pdf`, `informe_detective.json` e `informe_detective.md`) montando una carpeta del equipo anfitrión en `/app/output`:

- **En PowerShell (Windows):**
  ```powershell
  New-Item -ItemType Directory -Force -Path output | Out-Null
  docker run --rm --network none -v "${PWD}/output:/app/output" detective-estafas-digitales --text "Estimado cliente: Su cuenta sera suspendida hoy. Confirme su token en https://galicia-validacion.seguridad-bancaria.online" --output-dir /app/output
  ```
- **En Bash (Linux / macOS):**
  ```bash
  mkdir -p output
  docker run --rm --network none -v "$(pwd)/output:/app/output" detective-estafas-digitales --text "Estimado cliente: Su cuenta sera suspendida hoy. Confirme su token en https://galicia-validacion.seguridad-bancaria.online" --output-dir /app/output
  ```
Los archivos generados quedarán disponibles inmediatamente en la carpeta `./output/` de la computadora anfitriona. También se puede especificar una ruta puntual para el PDF con `--pdf-out /app/output/mi_informe.pdf`.

### 5. Ejecutar la suite de pruebas automatizadas dentro del contenedor
```bash
docker run --rm --network none --entrypoint pytest detective-estafas-digitales -v
```

### 6. Variables de entorno (Opcionales)
El proyecto **no requiere claves de API ni archivos `.env`** para funcionar (opera 100% local y sin llamadas a servicios externos). De forma opcional, se admiten las siguientes variables:
- `DETECTIVE_DIAGNOSTICS=true`: Activa la telemetría de diagnóstico e integridad en los reportes (incluye hash SHA-256 sin exponer datos personales). Ejemplo: `docker run --rm -e DETECTIVE_DIAGNOSTICS=true ...`
- `TESSERACT_CMD`: Ruta personalizada al binario de Tesseract (solo necesaria fuera de Docker si Tesseract no está en el `PATH` estándar).

---

## 🔒 6. Matriz de Seguridad y Privacidad

| Principio | Implementación en Código Python | Requiere Sandbox / Docker |
| :--- | :--- | :--- |
| **Zero Network** | El motor no importa sockets ni realiza peticiones HTTP/DNS. | Flag de Docker `--network none` a nivel kernel. |
| **Procesamiento en RAM** | Textos e imágenes se procesan en `io.BytesIO`. Cero persistencia en disco. | Contenedor efímero con `--read-only`. |
| **Anti-Decompression Bombs** | Límite estricto de 10 MB y 25 Megapíxeles en Pillow antes de la apertura. | Límite de memoria Docker (`--memory 128m`). |
| **Mitigación Prompt Injection** | El texto se trata como payload pasivo. Detección y reporte de intentos de secuestro. | Directivas fijas para el LLM en `SKILL.md`. |
| **Prevención Path Traversal** | Validación canónica con `resolve()`, verificación `is_relative_to` sobre lista blanca. | Sistema de archivos en solo lectura. |
| **Protección de Secretos** | Bloqueo incondicional de `.env`, `id_rsa`, `*.pem`, `*.key`. | No montar volúmenes con claves del anfitrión. |
| **Sin Ejecución Dinámica** | Cero `eval()`, `exec()` o llamadas construidas para la shell del SO. | Usuario sin privilegios root (UID 10001). |

---

## 🧪 7. Pruebas Automatizadas (67 Tests - 100% Aprobados)

Se construyó una suite exhaustiva de **67 pruebas automatizadas con pytest** que valida todas las capas del sistema:

```bash
.venv\Scripts\python.exe -m pytest -v
```

```text
============================= test session starts =============================
platform win32 -- Python 3.13.17, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\Asus\Documents\Diplomatura IA\detective-estafas-digitales
collected 67 items

tests/test_agent_skill_integration.py::test_agent_skill_manifest_validity PASSED [  2%]
tests/test_agent_skill_integration.py::test_agent_simulation_user_whatsapp_query PASSED [  5%]
tests/test_analyzer.py::test_detect_blocking_threat PASSED               [  8%]
tests/test_analyzer.py::test_detect_credential_harvesting PASSED         [ 11%]
tests/test_analyzer.py::test_detect_fake_rewards_and_advance_fee PASSED  [ 13%]
tests/test_analyzer.py::test_detect_debin_trick PASSED                   [ 16%]
tests/test_analyzer.py::test_detect_prompt_injection PASSED              [ 19%]
tests/test_analyzer.py::test_ambiguous_case_no_false_positive PASSED     [ 22%]
tests/test_analyzer.py::test_empty_or_whitespace_text PASSED             [ 25%]
tests/test_cli_and_stdin.py::test_cli_stdin_phishing_message PASSED      [ 27%]
tests/test_cli_and_stdin.py::test_cli_quotes_and_special_chars_via_stdin PASSED [ 30%]
tests/test_cli_and_stdin.py::test_cli_file_argument_execution PASSED     [ 33%]
tests/test_cli_and_stdin.py::test_cli_path_traversal_via_file_arg PASSED [ 36%]
tests/test_cli_and_stdin.py::test_cli_empty_stdin_produces_indeterminado PASSED [ 38%]
tests/test_cli_and_stdin.py::test_cli_missing_file_error PASSED          [ 41%]
tests/test_cli_and_stdin.py::test_cli_excessive_input_via_stdin PASSED   [ 44%]
tests/test_integration.py::test_caso_1_phishing_bancario_end_to_end PASSED [ 47%]
tests/test_integration.py::test_caso_2_premio_falso_end_to_end PASSED    [ 50%]
tests/test_integration.py::test_caso_3_mensaje_cotidiano_end_to_end PASSED [ 52%]
tests/test_integration.py::test_caso_4_url_enganyosa_end_to_end PASSED   [ 55%]
tests/test_integration.py::test_result_schema_compliance PASSED          [ 58%]
tests/test_integration.py::test_human_readable_report_generation PASSED  [ 61%]
tests/test_ocr.py::test_singleton_instance PASSED                         [ 63%]
tests/test_ocr.py::test_ocr_status_structure PASSED                       [ 65%]
tests/test_ocr.py::test_sanitize_extracted_text PASSED                    [ 68%]
tests/test_ocr.py::test_detect_url_anomalies_spaces PASSED                [ 70%]
tests/test_ocr.py::test_detect_url_anomalies_commas PASSED                [ 72%]
tests/test_ocr.py::test_detect_url_anomalies_vv PASSED                    [ 74%]
tests/test_ocr.py::test_detect_url_anomalies_leetspeak_digits PASSED     [ 76%]
tests/test_ocr.py::test_extract_text_when_tesseract_unavailable PASSED   [ 79%]
tests/test_ocr.py::test_extract_text_mocked_success PASSED               [ 81%]
tests/test_ocr.py::test_extract_text_mocked_error PASSED                 [ 83%]
tests/test_pdf_export.py::test_generate_pdf_from_phishing_report PASSED   [ 85%]
tests/test_pdf_export.py::test_generate_pdf_from_legitimate_report PASSED [ 88%]
tests/test_pdf_export.py::test_generate_pdf_from_indeterminate_report PASSED [ 90%]
tests/test_pdf_export.py::test_pdf_handles_spanish_accents_and_special_chars PASSED [ 92%]
tests/test_security.py::test_path_traversal_rejection_dotdot PASSED      [ 94%]
tests/test_security.py::test_path_traversal_absolute_external_path PASSED [ 96%]
tests/test_security.py::test_secret_files_blocked_proactively PASSED     [ 98%]
tests/test_security.py::test_disallowed_extension_rejected PASSED        [100%]
tests/test_security.py::test_excessive_input_handled_gracefully PASSED   [100%]
tests/test_security.py::test_prompt_injection_does_not_execute_commands PASSED [100%]
tests/test_urls.py::test_extract_urls PASSED                             [100%]
tests/test_urls.py::test_extract_urls_empty_text PASSED                  [100%]
tests/test_urls.py::test_is_ip_host PASSED                               [100%]
tests/test_urls.py::test_has_punycode_or_homoglyphs PASSED               [100%]
tests/test_urls.py::test_misleading_subdomains PASSED                    [100%]
tests/test_urls.py::test_analyze_single_url_with_ip PASSED               [100%]
tests/test_urls.py::test_analyze_single_url_credentials_in_url PASSED    [100%]
tests/test_urls.py::test_analyze_single_url_https_disclaimer PASSED      [100%]
tests/test_web_adapter.py::test_analyze_phishing_message PASSED           [100%]
tests/test_web_adapter.py::test_analyze_legitimate_message PASSED         [100%]
tests/test_web_adapter.py::test_empty_input_handling PASSED              [100%]
tests/test_web_adapter.py::test_whitespace_input_handling PASSED         [100%]
tests/test_web_adapter.py::test_input_mode_metadata_ocr PASSED           [100%]
tests/test_web_adapter.py::test_max_length_exceeded_defense PASSED       [100%]
tests/test_web_adapter.py::test_prompt_injection_safety PASSED           [100%]
tests/test_web_security.py::test_valid_png_image_accepted PASSED         [100%]
tests/test_web_security.py::test_valid_jpeg_image_accepted PASSED        [100%]
tests/test_web_security.py::test_valid_webp_image_accepted PASSED        [100%]
tests/test_web_security.py::test_empty_bytes_rejected PASSED             [100%]
tests/test_web_security.py::test_corrupted_bytes_rejected PASSED         [100%]
tests/test_web_security.py::test_disallowed_extension_rejected PASSED   [100%]
tests/test_web_security.py::test_fake_extension_magic_bytes_checked PASSED [100%]
tests/test_web_security.py::test_tiny_image_rejected PASSED             [100%]
tests/test_web_security.py::test_oversized_file_size_rejected PASSED     [100%]
tests/test_web_security.py::test_preprocessing_contrast_enhancement PASSED [100%]

============================= 67 passed in 2.69s ==============================
```

---

## ⚠️ 8. Honestidad Metodológica y Limitaciones

1. **Puntaje Heurístico (0-100):** Refleja la acumulación de indicadores de severidad identificados. **No representa una probabilidad matemática de fraude.**
2. **Ausencia de Señales != Mensaje Legítimo:** Que un mensaje obtenga **Riesgo BAJO (0/100)** indica que no se encontraron patrones conocidos, pero **no constituye un aval absoluto de autenticidad**.
3. **Análisis Estático Offline:** Por política Zero Network, el sistema no consulta bases WHOIS ni resuelve redirecciones en acortadores como `bit.ly`.
4. **Alcance del OCR:** El reconocimiento óptico depende de la resolución y contraste de la captura; por eso se implementó la revisión humana obligatoria antes del análisis.
5. **Alcance del Análisis:** El sistema analiza textos, capturas y enlaces; no realiza ingeniería inversa ni análisis dinámico sobre aplicaciones maliciosas (`.apk` o `.exe`).

---

## 🎓 9. Materiales Oficiales para la Defensa Oral

El repositorio incluye la documentación completa actualizada para la evaluación final:

- **Presentación Oficial (PowerPoint):** [Detective_Estafas_Digitales_Presentacion_FINAL.pptx](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/Detective_Estafas_Digitales_Presentacion_FINAL.pptx) (14 diapositivas profesionales, diseño Dark Slate / Cyan / Emerald con captura real de la aplicación web).
- **Guion de Defensa Oral (PDF):** [Guion_Defensa_Oral_Detective_Estafas_FINAL.pdf](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/Guion_Defensa_Oral_Detective_Estafas_FINAL.pdf) (Estructura sincronizada diapositiva por diapositiva para 6-8 minutos, banco ampliado de FAQs y hoja de comandos para la demo en vivo).
- **Guion de Defensa Oral (Word):** [Guion_Defensa_Oral_Detective_Estafas_FINAL.docx](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/Guion_Defensa_Oral_Detective_Estafas_FINAL.docx) (Versión editable con formato formal).
- **Manual de la Aplicación Web:** [docs/manual_web.md](file:///c:/Users/Asus/Documents/Diplomatura%20IA/detective-estafas-digitales/docs/manual_web.md).
