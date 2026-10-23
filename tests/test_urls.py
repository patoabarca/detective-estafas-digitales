"""
Pruebas Unitarias para el Módulo de Análisis Estático de URLs (test_urls.py).
Verifica que las URLs se analicen de manera puramente estática sin realizar
ninguna conexión de red externa, detectando anomalías y vectores comunes de engaño.
"""

import sys
from pathlib import Path
import pytest

# Agregar scripts/ al PYTHONPATH para importación directa
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from url_analyzer import (
    analyze_single_url,
    analyze_urls_in_text,
    check_misleading_subdomains,
    extract_urls,
    has_punycode_or_homoglyphs,
    is_ip_host,
)


def test_extract_urls():
    text = (
        "Visitá nuestro sitio en https://banco-seguro.online/login y también "
        "revisá http://192.168.1.1/admin o www.soporte-ayuda.site/index.html"
    )
    urls = extract_urls(text)
    assert len(urls) == 3
    assert "https://banco-seguro.online/login" in urls
    assert "http://192.168.1.1/admin" in urls
    assert any("soporte-ayuda.site" in u for u in urls)


def test_extract_urls_empty_text():
    assert extract_urls("") == []
    assert extract_urls("Este mensaje no contiene ningún link ni dirección web.") == []


def test_is_ip_host():
    assert is_ip_host("192.168.1.1") is True
    assert is_ip_host("10.0.0.5") is True
    assert is_ip_host("172.16.254.1") is True
    assert is_ip_host("bancogalicia.com.ar") is False
    assert is_ip_host("google.com") is False
    assert is_ip_host("") is False


def test_has_punycode_or_homoglyphs():
    # Dominio con prefijo Punycode
    assert has_punycode_or_homoglyphs("xn--banco-galcia-qob.com") is True
    # Dominio con caracter cirílico homóglifo (la 'а' es cirílica)
    assert has_punycode_or_homoglyphs("bаnco.com") is True
    # Dominio ASCII normal
    assert has_punycode_or_homoglyphs("bancogalicia.com.ar") is False


def test_misleading_subdomains():
    findings = check_misleading_subdomains("mercadopago.com.seguridad-cuenta.xyz")
    assert len(findings) > 0
    assert "mercadopago" in findings[0]
    assert "seguridad-cuenta.xyz" in findings[0]

    # Dominio legítimo oficial no debe marcarse como engañoso
    findings_official = check_misleading_subdomains("www.mercadopago.com")
    assert len(findings_official) == 0


def test_analyze_single_url_with_ip():
    res = analyze_single_url("http://192.168.0.55/login")
    assert res["is_ip_address"] is True
    assert res["scheme"] == "http"
    assert any("dirección IP" in f for f in res["findings"])
    assert any("sin cifrado" in f for f in res["findings"])


def test_analyze_single_url_credentials_in_url():
    res = analyze_single_url("https://victima:claveSecreta123@servidor-malicioso.com/auth")
    assert res["has_userinfo"] is True
    assert any("credenciales embebidas" in f for f in res["findings"])


def test_analyze_single_url_https_disclaimer():
    # Caso 4 del enunciado: Enlace con apariencia de dominio conocido pero estructura sospechosa
    res = analyze_single_url("https://santander.validacion-datos.online/login?token=abc12345")
    assert res["scheme"] == "https"
    # Debe aclarar que HTTPS no garantiza legitimidad
    assert any("NO garantiza legitimidad" in f for f in res["findings"])
    assert any("santander" in f for f in res["findings"])
    assert any("parámetros sensibles" in f for f in res["findings"])
