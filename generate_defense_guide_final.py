"""
Generador del Guion de Defensa Oral y Estructura de Presentación FINAL
para el proyecto 'Detective de Estafas Digitales'.

Genera dos versiones:
1. PDF: Guion_Defensa_Oral_Detective_Estafas_FINAL.pdf (ReportLab)
2. DOCX: Guion_Defensa_Oral_Detective_Estafas_FINAL.docx (python-docx)
"""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PDF = BASE_DIR / "Guion_Defensa_Oral_Detective_Estafas_FINAL.pdf"
OUTPUT_DOCX = BASE_DIR / "Guion_Defensa_Oral_Detective_Estafas_FINAL.docx"


# =========================================================================
# CONTENIDO DE LAS DIAPOSITIVAS Y GUION
# =========================================================================

SLIDES_DATA = [
    {
        "num": 1,
        "title": "Portada e Introducción al Proyecto",
        "content": [
            "<b>Título:</b> Detective de Estafas Digitales — Skill de IA Segura, Modular y Auditable.",
            "<b>Contexto académico:</b> Diplomatura en Inteligencia Artificial.",
            "<b>Eje central:</b> Agente Asistente • Análisis Determinístico • Mitigación de Inyección • Mínimo Privilegio."
        ],
        "script": (
            "«Buenas tardes profesor y compañeros. Hoy les presentamos 'Detective de Estafas Digitales', "
            "un proyecto desarrollado como trabajo práctico final de la Diplomatura en Inteligencia Artificial.\n\n"
            "El objetivo central fue construir una Skill real y auditable para agentes de IA que ayude a cualquier usuario "
            "a evaluar mensajes sospechosos de WhatsApp, SMS o correo, diseñada desde su arquitectura bajo principios "
            "estrictos de ciberseguridad: tratamiento de mensajes como datos no confiables, análisis estático sin salida a red "
            "y separación estricta entre la inteligencia del agente y la lógica de inspección.»"
        )
    },
    {
        "num": 2,
        "title": "El Problema: Ciberestafas y Manipulación Psicológica",
        "content": [
            "<b>Amenazas cotidianas:</b> Phishing y smishing masivo en Argentina (suplantación de Mercado Pago, Cuenta DNI, bancos y ANSES).",
            "<b>Ingeniería social:</b> Manipulación por miedo al bloqueo de cuentas, urgencias artificiales o falsos premios con DEBIN.",
            "<b>El desafío para los agentes de IA:</b> Analizar mensajes hostiles sin que el modelo sea manipulado por Prompt Injection ni forzado a visitar enlaces maliciosos."
        ],
        "script": (
            "«Todos los días vemos a personas caer en trampas digitales porque los estafadores apelan a la urgencia o al miedo "
            "de perder su cuenta o sus fondos. Pero cuando intentamos que un asistente de inteligencia artificial ayude en esta tarea, "
            "nos encontramos con un dilema de seguridad: el mensaje que analizamos puede contener trampas deliberadas destinadas "
            "a engañar al propio modelo de lenguaje.\n\n"
            "Además, una herramienta de asistencia jamás debería visitar enlaces desconocidos ni inventar probabilidades estadísticas "
            "sin sustento verificable.»"
        )
    },
    {
        "num": 3,
        "title": "Objetivo General y Alcance del MVP",
        "content": [
            "<b>Lo que SÍ hace el MVP:</b> Análisis estático de texto y enlaces, detección de patrones conocidos de fraude, mitigación activa de Prompt Injection, clasificación de riesgo explicable (BAJO/MEDIO/ALTO/INDET) y doble reporte (JSON formal + Markdown accesible).",
            "<b>Restricciones deliberadas:</b> Zero Network (cero peticiones HTTP/DNS), sin ejecución dinámica (prohibido eval/exec), sin dependencias externas para el motor funcional (100% biblioteca estándar de Python)."
        ],
        "script": (
            "«Para resolver este problema definimos un alcance muy claro: una herramienta determinística, local y explicable, "
            "sin dependencias externas en producción.\n\n"
            "Excluimos deliberadamente cualquier conexión a internet: si una herramienta analiza un link visitándolo, "
            "revela la dirección IP de la víctima y expone al sistema a exploits. Nuestro análisis es 100% estático, "
            "inspeccionando la sintaxis del mensaje y las URLs sin interactuar con los servidores atacantes.»"
        )
    },
    {
        "num": 4,
        "title": "Arquitectura General: Dónde Interviene la IA",
        "content": [
            "<b>Capa Cognitiva (LLM + Agente Antigravity):</b> Interpreta la intención del usuario en lenguaje natural, descubre la Skill mediante SKILL.md y traduce los resultados técnicos a recomendaciones empáticas.",
            "<b>Capa Determinística (Motor Python):</b> Analiza patrones léxicos, sintaxis de URLs y calcula un puntaje heurístico reproducible sin riesgo de alucinación.",
            "<b>Flujo de ejecución:</b> Usuario → Agente IA → SKILL.md → Motor Python (worker.py vía STDIN) → Reporte estructurado (JSON) → Agente IA → Explicación final al usuario."
        ],
        "script": (
            "«Acá llegamos al punto neurálgico del proyecto para la Diplomatura: ¿dónde interviene la Inteligencia Artificial?\n\n"
            "Nuestro agente utiliza inteligencia artificial para comprender la consulta del usuario en lenguaje natural "
            "y decidir cuándo activar la Skill según su manifiesto SKILL.md. Después, el motor Python analiza el mensaje "
            "mediante reglas verificables y devuelve un informe estructurado que el agente vuelve a interpretar para "
            "explicar los riesgos en lenguaje sencillo.\n\n"
            "No reemplazamos la IA por scripts, ni dejamos que la IA alucine indicadores: combinamos la capacidad lingüística "
            "del LLM con la precisión auditable de una herramienta determinística.»"
        )
    },
    {
        "num": 5,
        "title": "El Contrato del Agente: SKILL.md",
        "content": [
            "<b>Descubrimiento progresivo:</b> Encabezado YAML estándar (name, description) para que el agente reconozca cuándo activarla.",
            "<b>Tratamiento de datos no confiables:</b> El texto analizado se encapsula como 'Untrusted Data', nunca como instrucción operativa.",
            "<b>Comunicación robusta:</b> Se recomienda la invocación mediante STDIN para evitar interpolaciones de shell y fallas por comillas.",
            "<b>Mitigación de Prompt Injection:</b> Defensa en profundidad a nivel de directivas del agente y filtros de reglas en Python."
        ],
        "script": (
            "«El archivo SKILL.md funciona como el contrato operativo del agente. No solo le enseña en qué momento intervenir "
            "cuando el usuario le pega un mensaje sospechoso, sino que fija reglas de seguridad fundamentales:\n\n"
            "Primero, establece que todo contenido entrante es 'Untrusted Data' (información no confiable), lo que previene que el modelo "
            "obedezca órdenes maliciosas camufladas en el texto. Y segundo, prescribe la invocación mediante STDIN, "
            "lo que evita que comillas dobles o caracteres de shell rompan la ejecución o generen vulnerabilidades de inyección.»"
        )
    },
    {
        "num": 6,
        "title": "El Motor Funcional: Pipeline Python",
        "content": [
            "<b>worker.py:</b> Punto de entrada seguro; valida límites de entrada (máx. 15.000 chars), previene Path Traversal y lee vía STDIN o archivo.",
            "<b>analyzer.py:</b> Detección de coerción, urgencia, bloqueo, premios y patrones de inyección de instrucciones.",
            "<b>url_analyzer.py:</b> Extracción con Regex y auditoría sintáctica offline (IPs numéricas, subdominios falsos, homóglifos Punycode).",
            "<b>risk_classifier.py:</b> Cálculo de puntaje heurístico de severidad acumulada (0-100) y categoría de riesgo.",
            "<b>report_generator.py:</b> Generación de reportes duales con advertencia explícita sobre el significado del puntaje."
        ],
        "script": (
            "«En el motor funcional, cada módulo cumple una función técnica bien delimitada, sin dependencias de terceros:\n\n"
            "worker.py actúa como aduana de seguridad validando longitudes y rutas seguras; analyzer.py busca disparadores "
            "psicológicos de fraude e intentos de inyección; url_analyzer.py descompone cada enlace para detectar engaños sintácticos; "
            "risk_classifier.py asigna pesos transparentes; y report_generator.py emite la respuesta estructurada.\n\n"
            "Es importante destacar que estos módulos son herramientas determinísticas al servicio del agente, no modelos de IA en sí mismos.»"
        )
    },
    {
        "num": 7,
        "title": "Auditoría Estática de Enlaces (Zero Network)",
        "content": [
            "<b>Indicadores estructurales:</b> Direcciones IP literales (http://192.168.1.50/login), subdominios de suplantación (banco.galicia.com.dominio-trucho.xyz), homóglifos/punycode (xn--...), credenciales en URL y TLDs sospechosos (.xyz, .top, .online).",
            "<b>Aclaración educativa clave:</b> 'HTTPS NO significa seguro'. HTTPS solo cifra la conexión entre el usuario y el servidor. Un delincuente puede tramitar un certificado SSL gratuito en minutos; la comunicación viajará cifrada, pero irá directo al estafador."
        ],
        "script": (
            "«Una de las fortalezas más prácticas del proyecto es la auditoría estática de enlaces. Detectamos tácticas comunes "
            "como subdominios truchos o caracteres rusos disfrazados de letras latinas, todo de manera offline.\n\n"
            "Y además, incluimos un concepto educativo indispensable: 'HTTPS no significa seguro'. Muchos usuarios creen que el candado verde "
            "garantiza que el sitio es legítimo. Les explicamos que HTTPS solo cifra el canal; si el sitio pertenece a un estafador, "
            "las contraseñas viajarán cifradas, pero directamente a las manos del delincuente.»"
        )
    },
    {
        "num": 8,
        "title": "Seguridad y Niveles de Aislamiento",
        "content": [
            "<b>Restricciones en Código Python:</b> Path Traversal neutralizado (Path.resolve() limitado a carpeta segura), bloqueo estricto de secretos (.env, id_rsa), sanitización de caracteres y prohibición absoluta de eval/exec.",
            "<b>Aislamiento en Contenedor (Dockerfile implementado):</b> Imagen ligera python:3.13-slim, usuario no privilegiado (UID 10001), sistema de archivos de solo lectura (--read-only) y bloqueo total de red (--network none).",
            "<b>Honestidad técnica:</b> Docker aísla recursos del sistema operativo, pero no elimina todos los riesgos; la seguridad es multicapa."
        ],
        "script": (
            "«En ciberseguridad no existen las soluciones mágicas ni la 'inmunidad absoluta'. Por eso aplicamos una estrategia de defensa en profundidad.\n\n"
            "En el código Python prevenimos desbordamientos, bloqueamos el acceso a archivos del sistema y filtramos secretos. "
            "Y a nivel de infraestructura, implementamos un Dockerfile específico para empaquetar el motor con un usuario sin privilegios, "
            "sistema de archivos de solo lectura y el flag --network none, que garantiza a nivel del kernel de Linux que el contenedor "
            "no pueda abrir ningún socket a internet.»"
        )
    },
    {
        "num": 9,
        "title": "Batería de Pruebas Automatizadas con Pytest",
        "content": [
            "<b>Total ejecutado:</b> 36 pruebas automatizadas aprobadas en 1.05 segundos (100% de éxito).",
            "<b>Casos cubiertos:</b> Invocación real de CLI y STDIN, manejo de comillas y caracteres Unicode, rechazo de Path Traversal, entradas excesivas, mitigación de Prompt Injection, auditoría de URLs y flujo de integración Agente-Skill.",
            "<b>Transparencia:</b> Pasar el 100% de los tests no equivale a un 100% de cobertura del código ni garantiza detectar estafas no catalogadas."
        ],
        "script": (
            "«Para validar el proyecto no nos quedamos en pruebas manuales. Diseñamos una suite automatizada con pytest que creció "
            "de 27 a 36 pruebas unitarias y de integración, todas ejecutadas con éxito en apenas un segundo.\n\n"
            "Probamos la entrada por STDIN con textos de WhatsApp llenos de tildes y comillas, intentos de inyección de comandos, "
            "ataques de desbordamiento de caracteres y simulaciones completas del ciclo de vida del agente. "
            "Esto nos da certeza matemática de que las correcciones funcionan y no rompieron nada anterior.»"
        )
    },
    {
        "num": 10,
        "title": "Demostración Funcional y Casos Reales",
        "content": [
            "<b>Caso 1 (Phishing Bancario):</b> Alerta de bloqueo + enlace engañoso ➔ Riesgo ALTO (100/100).",
            "<b>Caso 2 (Prompt Injection):</b> Intento de cambiar el rol del agente ➔ Detectado y contenido.",
            "<b>Caso 3 (Mensaje Legítimo):</b> Conversación habitual ➔ Riesgo BAJO (0/100).",
            "<b>Aclaración imprescindible:</b> El resultado es un puntaje heurístico de riesgo (0-100), NO una probabilidad estadística. 100/100 significa acumulación de indicadores graves; 0/100 significa que no se detectaron patrones conocidos, sin que ello constituya un certificado absoluto de legitimidad."
        ],
        "script": (
            "«En la demostración práctica mostramos tres casos emblemáticos:\n\n"
            "El primero es un phishing bancario típico que acumula urgencia y un enlace falso, alcanzando un riesgo ALTO de 100/100.\n"
            "El segundo es un mensaje que incluye una inyección de instrucciones que intenta obligar al sistema a ignorar sus directivas, "
            "el cual es neutralizado y catalogado como amenaza.\n"
            "Y el tercero es un mensaje normal que arroja riesgo BAJO con 0/100.\n\n"
            "Queremos remarcar algo fundamental: 100/100 no es una probabilidad del 100% de estafa; es un puntaje heurístico "
            "basado en reglas. Del mismo modo, un 0/100 no garantiza al 100% que el remitente sea honesto; simplemente indica "
            "que no encontramos indicadores conocidos.»"
        )
    },
    {
        "num": 11,
        "title": "Honestidad Académica: Limitaciones del Sistema",
        "content": [
            "<b>Reglas heurísticas vs. Modelo propio:</b> El motor utiliza expresiones regulares y umbrales fijos; no fue entrenado con aprendizaje automático supervisado.",
            "<b>Falsos positivos y negativos:</b> Nuevas variantes de estafas que no utilicen las palabras clave o enlaces engañosos conocidos pueden no ser detectadas.",
            "<b>Análisis offline:</b> Al no resolver enlaces acortados (bit.ly) por seguridad, no es posible verificar la URL final de destino.",
            "<b>Formato de entrada:</b> Analiza únicamente texto plano; no procesa imágenes (OCR), archivos adjuntos PDF ni ejecutables APK."
        ],
        "script": (
            "«Siguiendo las mejores prácticas académicas, reconocemos con claridad las limitaciones del proyecto:\n\n"
            "El motor se basa en heurísticas expertas, no en una red neuronal entrenada con un dataset etiquetado. "
            "Esto significa que si un ciberdelincuente redacta una estafa con un vocabulario completamente novedoso o utiliza "
            "un enlace acortado que nosotros no abrimos por seguridad, el sistema puede arrojar un falso negativo.\n\n"
            "Tampoco procesamos capturas de pantalla ni archivos APK, ya que el alcance se limitó a texto plano.»"
        )
    },
    {
        "num": 12,
        "title": "Conclusiones y Aprendizajes",
        "content": [
            "<b>Aporte principal:</b> Demostración práctica de cómo integrar un LLM como interfaz cognitiva con un motor local determinístico y seguro.",
            "<b>Ciberseguridad aplicada:</b> Implementación real de mínimos privilegios, sanitización de entradas y defensa contra manipulaciones por inyección.",
            "<b>Lección de la Diplomatura:</b> Para construir agentes inteligentes verdaderamente útiles y confiables, la seguridad y la explicabilidad deben diseñarse desde el primer día."
        ],
        "script": (
            "«Para cerrar: este trabajo práctico nos permitió aplicar de forma concreta los temas de la Diplomatura. "
            "Aprendimos que la mejor arquitectura para un agente no consiste en delegar todo ciegamente a un modelo de lenguaje, "
            "sino en combinar su capacidad de comprensión con herramientas locales auditables, determinísticas y seguras.\n\n"
            "Logramos un sistema que protege al usuario final de las estafas y, al mismo tiempo, se protege a sí mismo "
            "de las amenazas digitales. Muchas gracias y quedo a disposición del profesor para la demostración y sus preguntas.»"
        )
    }
]

FAQS_DATA = [
    (
        "1. ¿Dónde está la inteligencia artificial?",
        "La IA reside en el Modelo de Lenguaje (LLM) operado por el Agente de Antigravity. El agente interpreta la consulta del usuario en lenguaje natural, comprende cuándo debe activar la Skill a partir de las instrucciones de SKILL.md, invoca el motor seguro y luego utiliza el informe estructurado devuelto para redactar una explicación empática y comprensible. El motor Python actúa como una herramienta determinística especializada al servicio de la IA."
    ),
    (
        "2. ¿Por qué no entrenaron una red neuronal?",
        "Porque para la auditoría de seguridad y la detección de estafas críticas se requiere explicabilidad 100% auditable y determinismo sin riesgo de alucinación. Si un modelo neuronal emite una probabilidad difusa, no podemos verificar el motivo exacto ni garantizar que una inyección de texto no distorsione el resultado. Las reglas heurísticas y el análisis sintáctico garantizan que la misma entrada produzca siempre exactamente la misma evaluación verificable."
    ),
    (
        "3. ¿Qué diferencia hay entre un agente y una Skill?",
        "El Agente es la entidad con capacidad de razonamiento basada en un LLM que interactúa con el usuario, toma decisiones y planifica acciones. La Skill es un paquete modular de capacidades (manifiesto SKILL.md, herramientas ejecutables y referencias) que amplía las facultades del agente para resolver una tarea específica con límites bien definidos."
    ),
    (
        "4. ¿Por qué utilizaron Python y reglas?",
        "Python es el estándar de facto en integración de agentes y ciencia de datos. Utilizamos la biblioteca estándar de Python (re, urllib.parse, argparse, json) porque permite ejecutar el motor sin dependencias de terceros, con tiempos de respuesta de milisegundos, consumo mínimo de memoria y una superficie de ataque reducida a cero vulnerabilidades de paquetes externos."
    ),
    (
        "5. ¿Qué significa una puntuación de 100/100?",
        "Significa que el mensaje acumuló suficientes indicadores de severidad grave (por ejemplo, amenazas de bloqueo + solicitud de claves + enlaces engañosos) para alcanzar el tope de la escala heurística. NO significa que exista una probabilidad matemática del 100% de que sea un fraude. De forma análoga, un 0/100 significa que no se detectaron patrones conocidos, no que el mensaje sea garantizadamente legítimo."
    ),
    (
        "6. ¿Cómo evitan que el agente obedezca instrucciones maliciosas?",
        "Mediante una estrategia de defensa en profundidad: en SKILL.md se instruye formalmente al agente a tratar todo mensaje del usuario como 'Untrusted Data' (datos no confiables). En el motor Python, el texto no se ejecuta jamás en shells ni con eval(), sino que se procesa como texto pasivo en memoria. Además, el módulo analyzer.py detecta patrones de inyección ('ignore previous instructions', etc.) y alerta inmediatamente de la amenaza."
    ),
    (
        "7. ¿Qué ocurre si el mensaje parece legítimo, pero en realidad es una estafa?",
        "El sistema arrojará un puntaje bajo o indeterminado, pero siempre emitirá una advertencia preventiva obligatoria: la ausencia de indicadores conocidos no es garantía absoluta de seguridad. Se recomienda al usuario verificar directamente por canales oficiales sin ingresar datos personales."
    ),
    (
        "8. ¿Por qué no verifican enlaces en Internet?",
        "Por la estricta política Zero Network adoptada en el proyecto. Visitar un enlace malicioso activo revela la dirección IP de la víctima al estafador, confirma que el número de teléfono o correo es válido y expone el sistema a posibles ataques o descargas automáticas de malware (drive-by downloads). Nuestro análisis es puramente estático y local."
    ),
    (
        "9. ¿Qué medidas de seguridad están efectivamente implementadas?",
        "En el código Python están verificadas: prevención de Path Traversal, bloqueo de archivos secretos (.env, id_rsa), límites estrictos de entrada (15.000 caracteres), entrada por STDIN sin interpolación de shell y ausencia de ejecución dinámica. A nivel de contenedor, se implementó el Dockerfile con usuario sin privilegios, sistema de archivos de solo lectura y aislamiento de red (--network none)."
    ),
    (
        "10. ¿Cómo demostraron que la Skill funciona dentro de Antigravity?",
        "La Skill se instaló en el repositorio estándar de Antigravity (.agents/skills/detective-estafas-digitales/SKILL.md). El agente lee el archivo de metadatos, reconoce las intenciones del usuario en lenguaje natural y sabe invocar el script scripts/worker.py vía STDIN. Verificamos tanto la invocación CLI con subprocesos como la integración lógica en las pruebas automatizadas."
    )
]

COMMANDS_DATA = [
    ("1. Demo Phishing Bancario", "Get-Content examples/phishing_bancario.txt | python scripts/worker.py --stdin", "Riesgo ALTO (100/100). Detecta subdominio falso y urgencia de bloqueo."),
    ("2. Demo Prompt Injection", "Get-Content examples/prompt_injection.txt | python scripts/worker.py --stdin", "Detecta inyección de instrucciones y la neutraliza sin ejecutar comandos."),
    ("3. Demo Mensaje Legítimo", "Get-Content examples/mensaje_legitimo.txt | python scripts/worker.py --stdin", "Riesgo BAJO (0/100) con advertencia de que la ausencia de señales no es garantía."),
    ("4. Salida en formato JSON", "Get-Content examples/phishing_bancario.txt | python scripts/worker.py --stdin --json", "Genera JSON conforme con schema oficial y score_type 'heuristic_severity_score'."),
    ("5. Batería de Tests Pytest", ".venv\\Scripts\\python.exe -m pytest -v", "Ejecuta las 36 pruebas automatizadas aprobadas en ~1.05s.")
]


# =========================================================================
# GENERADOR PDF CON REPORTLAB
# =========================================================================

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748B"))

        if self._pageNumber > 1:
            self.drawString(54, 750, "Detective de Estafas Digitales | Guion de Defensa Oral FINAL")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)

        footer_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(558, 36, footer_text)
        self.drawString(54, 36, "Diplomatura en Inteligencia Artificial — Trabajo Práctico Final")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 48, 558, 48)

        self.restoreState()


def build_pdf():
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    c_primary = colors.HexColor("#0F172A")
    c_accent = colors.HexColor("#0284C7")
    c_dark = colors.HexColor("#1E293B")
    c_speaker_bg = colors.HexColor("#F0F9FF")
    c_speaker_border = colors.HexColor("#0284C7")

    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=c_primary,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#475569"),
        spaceAfter=12
    )

    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=c_primary,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        "SlideHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=c_accent,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=c_dark,
        spaceAfter=3
    )

    bullet_style = ParagraphStyle(
        "CustomBullet",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        leftIndent=10,
        spaceAfter=2
    )

    speaker_style = ParagraphStyle(
        "SpeakerNote",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#0369A1"),
    )

    code_style = ParagraphStyle(
        "CodeText",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0F172A"),
    )

    story = []

    # Portada / Introducción
    story.append(Paragraph("🛡️ DETECTIVE DE ESTAFAS DIGITALES", title_style))
    story.append(Paragraph("<b>Guion de Defensa Oral y Estructura de la Presentación FINAL</b><br/>Diplomatura en Inteligencia Artificial — Exposición Académica", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=c_accent, spaceBefore=0, spaceAfter=10))

    intro_box = (
        "<b>📌 Pautas para la Exposición Oral (5 a 7 minutos):</b><br/>"
        "• <b>Tono:</b> Profesional, natural, fluido y técnicamente riguroso sin tecnicismos innecesarios.<br/>"
        "• <b>Idea Central a Transmitir:</b> <i>«Nuestro agente utiliza inteligencia artificial para comprender la consulta del usuario y decidir cuándo activar la Skill. Después, el motor Python analiza el mensaje mediante reglas verificables y devuelve un informe que el agente utiliza para explicar los riesgos en lenguaje sencillo.»</i><br/>"
        "• <b>Estructura:</b> Exposición de diapositivas (5-7 min), demostración de comandos en vivo (2 min) y preguntas del profesor."
    )
    t_intro = Table([[Paragraph(intro_box, body_style)]], colWidths=[504])
    t_intro.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(t_intro)
    story.append(Spacer(1, 12))

    # Diapositivas 1 a 12
    for item in SLIDES_DATA:
        card = []
        card.append(Paragraph(f"<b>DIAPOSITIVA {item['num']}: {item['title']}</b>", h2_style))
        card.append(Spacer(1, 3))

        card.append(Paragraph("<b>📊 Contenido visual proyectado:</b>", body_style))
        for bullet in item["content"]:
            card.append(Paragraph(f"• {bullet}", bullet_style))
        card.append(Spacer(1, 4))

        # Guion del orador
        script_formatted = item["script"].replace("\n\n", "<br/><br/>")
        spk_content = [
            Paragraph("<b>🗣️ GUION DEL ORADOR (Qué decir ante el profesor):</b>", ParagraphStyle("SpkH", parent=body_style, fontName="Helvetica-Bold", fontSize=8.5, textColor=c_accent)),
            Spacer(1, 2),
            Paragraph(script_formatted, speaker_style)
        ]
        t_spk = Table([[spk_content]], colWidths=[490])
        t_spk.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), c_speaker_bg),
            ('BOX', (0,0), (-1,-1), 1, c_speaker_border),
            ('LINELEFT', (0,0), (-1,-1), 3, c_accent),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        card.append(t_spk)
        card.append(Spacer(1, 10))

        story.append(KeepTogether(card))

    # Comandos para la Demo en Vivo
    story.append(PageBreak())
    story.append(Paragraph("💻 Chuleta de Comandos Rápidos para la Demo en Vivo", h1_style))
    story.append(Paragraph("Comandos recomendados en PowerShell para la demostración en vivo frente al tribunal:", body_style))
    story.append(Spacer(1, 6))

    cmd_rows = [
        [Paragraph("<b>Caso a Demostrar</b>", body_style), Paragraph("<b>Comando exacto a ejecutar</b>", body_style), Paragraph("<b>Aspecto clave a resaltar</b>", body_style)]
    ]
    for caso, cmd, detalle in COMMANDS_DATA:
        cmd_rows.append([
            Paragraph(f"<b>{caso}</b>", body_style),
            Paragraph(f"<code>{cmd}</code>", code_style),
            Paragraph(detalle, bullet_style)
        ])

    t_cmds = Table(cmd_rows, colWidths=[110, 220, 174])
    t_cmds.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_cmds)
    story.append(Spacer(1, 14))

    # 10 Preguntas y Respuestas del Profesor
    story.append(Paragraph("❓ Respuestas Preparadas a las 10 Preguntas Clave del Profesor", h1_style))
    story.append(Paragraph("Respuestas breves, directas y rigurosas a las preguntas más probables del tribunal:", body_style))
    story.append(Spacer(1, 6))

    for q, a in FAQS_DATA:
        faq_box = [
            Paragraph(f"<b>{q}</b>", ParagraphStyle("QH", parent=body_style, fontName="Helvetica-Bold", fontSize=9.5, textColor=c_primary)),
            Spacer(1, 2),
            Paragraph(a, ParagraphStyle("QA", parent=body_style, fontName="Helvetica", fontSize=9, leading=13, textColor=colors.HexColor("#334155")))
        ]
        t_faq = Table([[faq_box]], colWidths=[504])
        t_faq.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#E2E8F0")),
            ('LINELEFT', (0,0), (-1,-1), 3, colors.HexColor("#10B981")),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(KeepTogether(t_faq))
        story.append(Spacer(1, 5))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Documento PDF generado exitosamente en: {OUTPUT_PDF}")


# =========================================================================
# GENERADOR DOCX CON PYTHON-DOCX
# =========================================================================

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)


def set_cell_left_border(cell, color_hex="0284C7", sz="24"):
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="none"/>'
        f'<w:left w:val="single" w:sz="{sz}" w:space="0" w:color="{color_hex}"/>'
        f'<w:bottom w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(tcBorders)


def build_docx():
    doc = docx.Document()

    # Configurar márgenes
    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Título principal
    title_p = doc.add_paragraph()
    r_title = title_p.add_run("🛡️ DETECTIVE DE ESTAFAS DIGITALES")
    r_title.bold = True
    r_title.font.name = "Calibri"
    r_title.font.size = Pt(22)
    r_title.font.color.rgb = RGBColor(15, 23, 42)

    sub_p = doc.add_paragraph()
    r_sub = sub_p.add_run("Guion de Defensa Oral y Estructura de la Presentación FINAL\nDiplomatura en Inteligencia Artificial — Exposición Académica")
    r_sub.font.name = "Calibri"
    r_sub.font.size = Pt(11)
    r_sub.font.color.rgb = RGBColor(71, 85, 105)

    # Caja de pautas clave
    t_intro = doc.add_table(rows=1, cols=1)
    t_intro.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_intro = t_intro.cell(0, 0)
    set_cell_background(c_intro, "F1F5F9")
    p_intro = c_intro.paragraphs[0]
    p_intro.paragraph_format.space_before = Pt(4)
    p_intro.paragraph_format.space_after = Pt(4)
    r_in = p_intro.add_run(
        "📌 Pautas para la Exposición Oral (5 a 7 minutos):\n"
        "• Tono: Profesional, natural, fluido y técnicamente riguroso sin tecnicismos innecesarios.\n"
        "• Idea Central a Transmitir: «Nuestro agente utiliza inteligencia artificial para comprender la consulta del usuario y decidir cuándo activar la Skill. Después, el motor Python analiza el mensaje mediante reglas verificables y devuelve un informe que el agente utiliza para explicar los riesgos en lenguaje sencillo.»\n"
        "• Estructura: Exposición de diapositivas (5-7 min), demostración en vivo (2 min) y preguntas del tribunal."
    )
    r_in.font.name = "Calibri"
    r_in.font.size = Pt(9.5)
    r_in.font.color.rgb = RGBColor(30, 41, 59)

    doc.add_paragraph()

    # Slides 1 a 12
    for item in SLIDES_DATA:
        # Título de Diapositiva
        h_slide = doc.add_paragraph()
        h_slide.paragraph_format.space_before = Pt(12)
        h_slide.paragraph_format.space_after = Pt(2)
        r_sh = h_slide.add_run(f"DIAPOSITIVA {item['num']}: {item['title']}")
        r_sh.bold = True
        r_sh.font.name = "Calibri"
        r_sh.font.size = Pt(13)
        r_sh.font.color.rgb = RGBColor(2, 132, 199)

        # Contenido visual
        p_vis = doc.add_paragraph()
        p_vis.paragraph_format.space_before = Pt(2)
        p_vis.paragraph_format.space_after = Pt(2)
        r_vh = p_vis.add_run("📊 Contenido visual proyectado:")
        r_vh.bold = True
        r_vh.font.name = "Calibri"
        r_vh.font.size = Pt(10)
        r_vh.font.color.rgb = RGBColor(15, 23, 42)

        for bullet in item["content"]:
            p_b = doc.add_paragraph(style='List Bullet')
            p_b.paragraph_format.space_before = Pt(1)
            p_b.paragraph_format.space_after = Pt(1)
            # Limpiar etiquetas HTML simples
            clean_b = bullet.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
            r_b = p_b.add_run(clean_b)
            r_b.font.name = "Calibri"
            r_b.font.size = Pt(9.5)
            r_b.font.color.rgb = RGBColor(51, 65, 85)

        # Caja de guion del orador
        t_spk = doc.add_table(rows=1, cols=1)
        t_spk.alignment = WD_TABLE_ALIGNMENT.CENTER
        c_spk = t_spk.cell(0, 0)
        set_cell_background(c_spk, "F0F9FF")
        set_cell_left_border(c_spk, "0284C7", "24")

        p_spk_head = c_spk.paragraphs[0]
        p_spk_head.paragraph_format.space_before = Pt(4)
        p_spk_head.paragraph_format.space_after = Pt(2)
        r_sph = p_spk_head.add_run("🗣️ GUION DEL ORADOR (Qué decir ante el profesor):")
        r_sph.bold = True
        r_sph.font.name = "Calibri"
        r_sph.font.size = Pt(9)
        r_sph.font.color.rgb = RGBColor(2, 132, 199)

        p_spk_body = c_spk.add_paragraph()
        p_spk_body.paragraph_format.space_before = Pt(2)
        p_spk_body.paragraph_format.space_after = Pt(4)
        r_spb = p_spk_body.add_run(item["script"])
        r_spb.italic = True
        r_spb.font.name = "Calibri"
        r_spb.font.size = Pt(9.5)
        r_spb.font.color.rgb = RGBColor(3, 105, 161)

        doc.add_paragraph()

    # Comandos para la demo
    doc.add_page_break()
    h_cmd = doc.add_paragraph()
    r_ch = h_cmd.add_run("💻 Chuleta de Comandos Rápidos para la Demo en Vivo")
    r_ch.bold = True
    r_ch.font.name = "Calibri"
    r_ch.font.size = Pt(14)
    r_ch.font.color.rgb = RGBColor(15, 23, 42)

    t_cmd = doc.add_table(rows=len(COMMANDS_DATA) + 1, cols=3)
    t_cmd.alignment = WD_TABLE_ALIGNMENT.CENTER

    headers = ["Caso a Demostrar", "Comando exacto a ejecutar", "Aspecto clave a resaltar"]
    for i, h in enumerate(headers):
        c = t_cmd.cell(0, i)
        set_cell_background(c, "E2E8F0")
        p = c.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.name = "Calibri"
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(15, 23, 42)

    for row_idx, (caso, cmd, detalle) in enumerate(COMMANDS_DATA, start=1):
        c0 = t_cmd.cell(row_idx, 0)
        c1 = t_cmd.cell(row_idx, 1)
        c2 = t_cmd.cell(row_idx, 2)

        r0 = c0.paragraphs[0].add_run(caso)
        r0.bold = True
        r0.font.name = "Calibri"
        r0.font.size = Pt(9)

        r1 = c1.paragraphs[0].add_run(cmd)
        r1.font.name = "Consolas"
        r1.font.size = Pt(8.5)

        r2 = c2.paragraphs[0].add_run(detalle)
        r2.font.name = "Calibri"
        r2.font.size = Pt(9)

    doc.add_paragraph()

    # 10 Preguntas y Respuestas
    h_faq = doc.add_paragraph()
    r_fh = h_faq.add_run("❓ Respuestas Preparadas a las 10 Preguntas Clave del Profesor")
    r_fh.bold = True
    r_fh.font.name = "Calibri"
    r_fh.font.size = Pt(14)
    r_fh.font.color.rgb = RGBColor(15, 23, 42)

    for q, a in FAQS_DATA:
        t_f = doc.add_table(rows=1, cols=1)
        t_f.alignment = WD_TABLE_ALIGNMENT.CENTER
        cf = t_f.cell(0, 0)
        set_cell_background(cf, "F8FAFC")
        set_cell_left_border(cf, "10B981", "24")

        pf_q = cf.paragraphs[0]
        pf_q.paragraph_format.space_before = Pt(3)
        pf_q.paragraph_format.space_after = Pt(2)
        rq = pf_q.add_run(q)
        rq.bold = True
        rq.font.name = "Calibri"
        rq.font.size = Pt(9.5)
        rq.font.color.rgb = RGBColor(15, 23, 42)

        pf_a = cf.add_paragraph()
        pf_a.paragraph_format.space_before = Pt(1)
        pf_a.paragraph_format.space_after = Pt(3)
        ra = pf_a.add_run(a)
        ra.font.name = "Calibri"
        ra.font.size = Pt(9)
        ra.font.color.rgb = RGBColor(51, 65, 85)

        doc.add_paragraph()

    doc.save(str(OUTPUT_DOCX))
    print(f"Documento DOCX generado exitosamente en: {OUTPUT_DOCX}")


if __name__ == "__main__":
    build_pdf()
    build_docx()
