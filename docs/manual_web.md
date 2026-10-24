# 📖 Manual de Uso y Arquitectura: Mini Aplicación Web Streamlit con OCR
## Detective de Estafas Digitales — Diplomatura en Inteligencia Artificial

---

## 🎯 1. Introducción y Propósito

El **Detective de Estafas Digitales** nació como una Skill de ciberseguridad para agentes inteligentes en **Google Antigravity**. Para acercar esta herramienta a personas sin conocimientos técnicos que no utilizan terminales ni consolas de desarrollo, desarrollamos una **mini aplicación web interactiva en Streamlit**.

La aplicación web permite evaluar mensajes dudosos en dos modalidades:
1. **Modalidad A (Texto directo):** Copiar y pegar el texto de un WhatsApp, SMS, correo o publicación.
2. **Modalidad B (Captura de pantalla):** Cargar una imagen del mensaje para que el sistema extraiga el texto mediante **OCR local** (Tesseract) y permita su revisión antes del análisis.

Ambas modalidades procesan la información utilizando **el mismo motor determinístico en Python** (`scripts/`), garantizando total explicabilidad, cero alucinaciones y cero conexiones salientes a internet (Zero Network).

---

## 🏛️ 2. Arquitectura General: Dos Vías, Un Mismo Motor

El proyecto mantiene dos vías de acceso completamente independientes que comparten la misma lógica central:

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

> [!IMPORTANT]
> **Honestidad Técnica:** La aplicación web **NO** afirma utilizar el LLM de Antigravity ni realiza llamadas a APIs externas de OpenAI, Gemini u otros servicios en la nube. Opera de forma 100% determinística y local. El OCR utiliza un modelo preentrenado estándar de código abierto (Tesseract); no se entrenó una red neuronal propia.

---

## 💻 3. Requisitos del Sistema e Instalación

### 3.1 Entorno de Ejecución
- **Sistema Operativo:** Windows 10/11, Linux o macOS.
- **Python:** Versión 3.10 o superior (validado en Python 3.13 en Windows).

### 3.2 Dependencias de Python
Las dependencias de la aplicación web se encuentran separadas en `requirements-web.txt` para mantener el motor base libre de paquetes externos:

```bash
# Activar el entorno virtual
.venv\Scripts\activate   # En Windows
# source .venv/bin/activate  # En Linux/macOS

# Instalar dependencias de la aplicación web
pip install -r requirements-web.txt
```

### 3.3 Instalación y Configuración de Tesseract OCR

Tesseract es el motor de reconocimiento óptico de caracteres que se ejecuta de forma local y offline.

#### Instalación en Windows:
1. Abrir una terminal de PowerShell y ejecutar:
   ```powershell
   winget install UB-Mannheim.TesseractOCR
   ```
2. Durante la instalación (o descargando el instalador oficial de GitHub), verificar marcar la opción **Additional language data (download) ➔ Spanish**.
3. Por defecto, Tesseract se instalará en:
   `C:\Program Files\Tesseract-OCR\tesseract.exe`
4. El servicio `web/ocr_service.py` detecta automáticamente esta ruta en Windows. Si estuviera en una ubicación personalizada, se puede configurar mediante la variable de entorno:
   ```powershell
   $env:TESSERACT_CMD = "C:\Ruta\Personalizada\tesseract.exe"
   ```

#### Modo Asistido (Sin Tesseract Instalado):
Si Tesseract no estuviera instalado en el equipo anfitrión, la aplicación **no se interrumpe**: detecta la situación, muestra un cartel informativo con la guía de instalación y permite al usuario cargar la imagen y transcribir/pegar el texto manualmente en el editor interactivo para continuar con el análisis.

---

## 🚀 4. Puesta en Marcha de la Aplicación Web

Para iniciar el servidor local de Streamlit:

```bash
# Ejecutar desde la raíz del proyecto
streamlit run app.py
```

La aplicación se iniciará automáticamente en el navegador predeterminado en:
`http://localhost:8501`

---

## 📱 5. Guía de Uso Paso a Paso

### 5.1 Modalidad A: Pegar Texto Directo
1. Ingresar a la pestaña **📝 Pegar Texto**.
2. Pegar el contenido del mensaje sospechoso en el cuadro de texto. El contador inferior verifica que no se superen los 15.000 caracteres.
3. Hacer clic en **🔍 Analizar Mensaje**.
4. Revisar la tarjeta de riesgo, la explicación en lenguaje sencillo, las evidencias detectadas, la auditoría estática de enlaces y las recomendaciones preventivas.

### 5.2 Modalidad B: Cargar Captura de Pantalla + OCR
1. Ingresar a la pestaña **📷 Subir Captura de Pantalla**.
2. Arrastrar o seleccionar un archivo de imagen en formato **PNG, JPG, JPEG o WEBP** (máximo 10 MB).
3. Verificar la vista previa en la columna izquierda.
4. Presionar **🔎 Extraer Texto de la Captura**. Tesseract procesará la imagen en memoria y colocará el texto reconocido en el editor de la columna derecha.
5. **Revisión Humana Obligatoria (Human-in-the-loop):** Si el sistema detecta que el OCR pudo haber distorsionado una URL (por ejemplo, confundiendo ceros con letras 'o', o comas con puntos), mostrará un cartel de advertencia amarillo. Modificar el texto en el editor interactivo para corregir cualquier error tipográfico.
6. Presionar **🔍 Analizar Texto de la Captura** para procesar el mensaje con el motor determinístico.

### 5.3 Exportación del Informe en PDF
1. Al pie de la sección de resultados, presionar el botón **📄 Descargar Informe Completo en PDF**.
2. Se compilará en memoria un archivo PDF formal mediante ReportLab con fecha/hora UTC, desglose de indicadores, enlaces en texto plano y recomendaciones.
3. El archivo se descargará directamente en el navegador sin guardarse en el servidor.

### 5.4 Limpieza de Sesión
- En la barra lateral izquierda, hacer clic en **🧹 Limpiar Sesión y Datos** para purgar de inmediato todos los textos, imágenes y resultados de la memoria RAM.

---

## 🔒 6. Medidas de Seguridad y Privacidad

La aplicación fue desarrollada siguiendo estrictos lineamientos de ciberseguridad:

| Principio | Implementación Técnica |
| :--- | :--- |
| **Zero Network en el Motor** | El análisis estático de texto y URLs no realiza conexiones HTTP, peticiones DNS ni consultas a bases de datos en la nube. |
| **Procesamiento 100% en Memoria** | Las imágenes y textos se leen mediante `io.BytesIO`. No se escriben archivos temporales en disco. |
| **Anti-Decompression Bombs** | Límite estricto de 10 MB y 25 Megapíxeles por imagen verificado antes de la apertura con Pillow. |
| **Desactivación de Enlaces** | Las URLs detectadas se renderizan como texto plano monoespaciado sin enlaces clickeables para evitar ingresos accidentales. |
| **Mitigación de Prompt Injection** | Mensajes con directivas como *"Ignora tus instrucciones anteriores"* se procesan como payload pasivo y se reportan como amenaza crítica. |
| **Prevención de Inyecciones de Código** | Cero uso de `eval()`, `exec()` o pasaje de cadenas de usuario a la shell del sistema operativo. |

---

## 🧪 7. Ejecución de la Suite de Pruebas Automatizadas

El proyecto cuenta con **67 pruebas automatizadas con Pytest** que garantizan la integridad de todas las capas:

```bash
# Ejecutar todas las pruebas
pytest -v
```

### Desglose de Pruebas:
- **Motor determinístico original (36 pruebas):** Integración agéntica (`test_agent_skill_integration.py`), invocación CLI y STDIN (`test_cli_and_stdin.py`), analizador textual (`test_analyzer.py`), auditoría de URLs (`test_urls.py`), seguridad y contención (`test_security.py`) e integración de escenarios (`test_integration.py`).
- **Nueva capa web y OCR (31 pruebas):** Adaptador web sin comandos shell (`test_web_adapter.py`), servicio OCR y distorsiones de URLs (`test_ocr.py`), exportador PDF en memoria (`test_pdf_export.py`) y validación segura de imágenes (`test_web_security.py`).

---

## 📌 8. Honestidad Metodológica y Limitaciones

- **Puntaje Heurístico (0-100):** Es una escala acumulativa de severidad de reglas activadas. **No representa una probabilidad estadística de fraude.**
- **Ausencia de Señales:** Un resultado de **Riesgo BAJO (0/100)** indica que no se identificaron indicadores conocidos en el texto, pero **no constituye un certificado de autenticidad absoluta**.
- **Limitaciones del OCR:** El reconocimiento óptico depende de la nitidez de la captura. Capturas borrosas, tipografías caligráficas o fondos con mucho ruido visual pueden generar errores tipográficos.
- **Alcance del Análisis:** La herramienta analiza mensajes textuales, capturas y enlaces; no analiza troyanos bancarios compilados en archivos ejecutables (.apk / .exe).
