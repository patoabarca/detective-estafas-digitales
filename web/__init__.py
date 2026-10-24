"""
Paquete web para Detective de Estafas Digitales.
Contiene el adaptador del motor, servicios de procesamiento de imágenes, OCR y exportación de informes PDF.
"""

from .analysis_adapter import analyze_text
from .image_processor import validate_and_load_image, preprocess_image_for_ocr
from .ocr_service import OCRService, get_ocr_service
from .pdf_exporter import generate_pdf_report

__all__ = [
    "analyze_text",
    "validate_and_load_image",
    "preprocess_image_for_ocr",
    "OCRService",
    "get_ocr_service",
    "generate_pdf_report",
]
