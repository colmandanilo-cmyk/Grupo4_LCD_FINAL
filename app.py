"""
app.py — Radar de Oportunidades en Compras Públicas · Data App (v5).

Rediseño visual alineado con la presentación final:
- paleta exacta de la PPT: azul petróleo, naranja, lila y morado;
- las cinco preguntas de negocio quedan visibles en todo momento;
- cada categoría seleccionada responde Q1-Q5 con números grandes;
- el recorrido conserva la lógica del proyecto: dónde competir → qué está
  abierto → qué necesito para postular;
- no se cambian Parquet, columnas, reglas de negocio ni cálculo del índice.

Ejecución local:
    streamlit run app.py
"""

from __future__ import annotations

from html import escape
from datetime import datetime
from pathlib import Path
import json
import re
import unicodedata

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import config
from formalidades import cargar_catalogo, requisitos_por_objeto

st.set_page_config(
    page_title="Radar de Oportunidades en Compras Públicas",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

MONEDA = "S/"
SEACE_BUSCADORES_URL = (
    "https://www.gob.pe/institucion/oece/pages/"
    "7505-consultar-los-buscadores-publicos-del-sistema-electronico-"
    "de-contrataciones-del-estado-seace"
)

# ---------------------------------------------------------------------------
# Identidad visual tomada de la presentación T2
# ---------------------------------------------------------------------------
AZUL = "#004064"
NARANJA = "#FF6B2B"
MORADO = "#22265D"
LILA = "#DADBF1"
FONDO = "#F4F7F9"
BLANCO = "#FFFFFF"
TINTA = "#272525"
APAGADO = "#667684"
BORDE = "#D0D1E7"
VERDE = "#2F9E65"
AMBAR = "#C18A20"
GRIS = "#869AB4"

# Rubros de negocio: agrupan palabras que aparecen en la descripción CUBSO.
# Reemplazan a la búsqueda libre para que el usuario filtre por su giro
# comercial sin tener que adivinar cómo está escrita la categoría.
# Las palabras van sin tildes y en minúscula porque se comparan contra el
# texto ya normalizado por normalizar_busqueda().
RUBROS_NEGOCIO: dict[str, list[str]] = {
    "Alimentos, catering y víveres": [
        "aliment", "catering", "viveres", "abarrote", "carne$", "pollo",
        "pescado", "lacteo", "leche$", "queso", "huevo", "pan$", "panificad",
        "arroz", "azucar", "aceite", "fruta", "verdura", "hortaliza",
        "menestra", "bebida", "agua de mesa", "racion", "desayuno", "almuerzo",
        "refrigerio", "comedor", "cocina", "fideo", "conserva$", "cereal",
    ],
    "Limpieza e higiene": [
        "limpieza", "higien", "desinfec", "detergente", "lejia", "jabon",
        "papel toalla", "papel higienico", "fumigac", "residuo solido",
        "escoba", "trapeador",
    ],
    "Seguridad y vigilancia": [
        "vigilancia", "segurid", "resguardo", "alarma", "camara de video",
        "extintor", "contra incendio",
    ],
    "Construcción, obras y mantenimiento": [
        "obra$", "construc", "manten", "reparac", "pintura", "albanil",
        "cemento", "ladrillo", "fierro", "agregado", "instalacion",
        "acabado", "carpinteria", "gasfiteria", "electricid",
    ],
    "Mobiliario y equipamiento": [
        "mobiliario", "mueble", "escritorio", "silla", "mesa$", "estante",
        "armario", "equipamiento", "colchon",
    ],
    "Textiles, uniformes y calzado": [
        "textil", "uniforme", "prenda", "calzado", "zapat", "bota$",
        "chaleco", "camisa", "polo$", "tela$", "confeccion", "mandil",
    ],
    "Tecnología e informática": [
        "informat", "computo", "computad", "laptop", "software", "hardware",
        "impresora", "servidor", "red de datos", "tecnolog", "telecomunic",
        "sistema de informacion", "licencia de", "soporte tecnico",
    ],
    "Papelería y útiles de oficina": [
        "papel bond", "utiles de oficina", "utiles de escritorio", "tinta",
        "toner", "cuaderno", "archivador", "folder", "lapicero",
        "servicio de impresion", "fotocopia", "millar",
    ],
    "Salud y material médico": [
        "medicament", "salud", "farmac", "hospital", "insumo medico",
        "material medico", "laboratorio", "odontolog", "enfermeria",
        "quirurgic", "reactivo",
    ],
    "Transporte, combustible y logística": [
        "transporte", "flete", "logistic", "combustible", "gasohol", "diesel",
        "vehicul", "alquiler de vehiculo", "courier", "neumatico", "llanta",
    ],
    "Servicios profesionales y consultoría": [
        "consultor", "asesor", "capacitac", "auditor", "supervision de obra",
        "elaboracion de estudio", "expediente tecnico", "estudio de",
        "servicio profesional",
    ],
    "Agropecuario, semillas e insumos": [
        "semilla", "fertilizante", "abono", "agricol", "pecuari", "ganado",
        "vacuna animal", "alimento balanceado", "riego", "vivero",
    ],
}

COLOR_BANDA = {
    "Sin adjudicatario vigente": NARANJA,
    "Poca competencia (1-2)": VERDE,
    "Competencia media (3-5)": AMBAR,
    "Disputado (>5)": GRIS,
    "Competencia no determinada": "#C3CEDB",
}

st.markdown(
    f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

      :root {{
        --ro-azul:{AZUL}; --ro-naranja:{NARANJA}; --ro-morado:{MORADO};
        --ro-lila:{LILA}; --ro-fondo:{FONDO}; --ro-tinta:{TINTA};
        --ro-apagado:{APAGADO}; --ro-borde:{BORDE};
        --ro-verde:{VERDE}; --ro-ambar:{AMBAR}; --ro-gris:{GRIS};
      }}

      .stApp {{ background:{FONDO}; color:{TINTA}; font-family: 'Inter', sans-serif; }}
      .block-container {{ max-width:1480px; padding-top:0.8rem; padding-bottom:3rem; }}
      #MainMenu {{ visibility:hidden; }}
      footer {{ visibility:hidden; }}
      header[data-testid="stHeader"] {{ background:transparent; }}

      h1, h2, h3, h4 {{ letter-spacing:-0.025em; color:{TINTA}; font-family: 'Inter', sans-serif; }}
      p, label, .stCaption {{ color:{APAGADO}; font-family: 'Inter', sans-serif; }}

      @keyframes fadeInUp {{
        from {{ opacity: 0; transform: translateY(30px); }}
        to {{ opacity: 1; transform: translateY(0); }}
      }}
      @keyframes fadeIn {{
        from {{ opacity: 0; }}
        to {{ opacity: 1; }}
      }}
      @keyframes slideInRight {{
        from {{ opacity: 0; transform: translateX(-20px); }}
        to {{ opacity: 1; transform: translateX(0); }}
      }}
      @keyframes pulse {{
        0%, 100% {{ transform: scale(1); }}
        50% {{ transform: scale(1.03); }}
      }}
      @keyframes shimmer {{
        0% {{ background-position: -200% 0; }}
        100% {{ background-position: 200% 0; }}
      }}
      @keyframes float {{
        0%, 100% {{ transform: translateY(0px); }}
        50% {{ transform: translateY(-8px); }}
      }}

      .ro-hero {{
        background: linear-gradient(135deg, {AZUL} 0%, #0a2540 40%, {MORADO} 100%);
        border-radius: 24px;
        padding: 40px 36px 36px 36px;
        color: #fff;
        display: flex;
        align-items: center;
        gap: 28px;
        box-shadow: 0 20px 60px rgba(0,64,100,.18), 0 0 0 1px rgba(255,255,255,.08) inset;
        margin-bottom: 20px;
        position: relative;
        overflow: hidden;
        animation: fadeInUp 0.8s ease-out;
      }}
      .ro-hero::before {{
        content: '';
        position: absolute;
        top: -60%;
        right: -5%;
        width: 500px;
        height: 500px;
        background: radial-gradient(circle, rgba(255,107,43,0.12) 0%, transparent 65%);
        border-radius: 50%;
        animation: float 6s ease-in-out infinite;
      }}
      .ro-hero::after {{
        content: '';
        position: absolute;
        bottom: -30%;
        left: -10%;
        width: 400px;
        height: 400px;
        background: radial-gradient(circle, rgba(218,219,241,0.08) 0%, transparent 60%);
        border-radius: 50%;
      }}
      .ro-hero-left {{ min-width: 0; position: relative; z-index: 1; }}
      .ro-kicker {{
        display: inline-block;
        background: rgba(255,107,43,0.9);
        color: #fff;
        border-radius: 8px;
        padding: 6px 14px;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: .08em;
        margin-bottom: 14px;
        text-transform: uppercase;
        box-shadow: 0 4px 15px rgba(255,107,43,0.3);
        animation: slideInRight 0.6s ease-out 0.2s both;
      }}
      .ro-hero-title {{
        font-size: 38px;
        line-height: 1.05;
        font-weight: 900;
        color: #fff;
        letter-spacing: -.04em;
        margin: 0;
        animation: fadeInUp 0.7s ease-out 0.3s both;
      }}
      .ro-hero-title span {{
        color: {NARANJA};
        text-shadow: 0 2px 20px rgba(255,107,43,0.3);
      }}
      .ro-hero-sub {{
        color: #A8C4D9;
        font-size: 15px;
        margin-top: 12px;
        line-height: 1.5;
        max-width: 600px;
        animation: fadeInUp 0.7s ease-out 0.4s both;
      }}
      .ro-hero-meta {{
        margin-left: auto;
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        justify-content: flex-end;
        max-width: 480px;
        position: relative;
        z-index: 1;
        animation: fadeInUp 0.7s ease-out 0.5s both;
      }}
      .ro-chip {{
        background: rgba(255,255,255,.08);
        color: #fff;
        border: 1px solid rgba(255,255,255,.18);
        border-radius: 10px;
        padding: 10px 14px;
        font-size: 12px;
        font-weight: 700;
        white-space: nowrap;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
      }}
      .ro-chip:hover {{
        background: rgba(255,255,255,.15);
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(0,0,0,0.15);
      }}

      .ro-questions-wrap {{
        background: linear-gradient(145deg, {AZUL} 0%, #0a3050 100%);
        border-radius: 20px;
        padding: 28px;
        margin: 14px 0 18px 0;
        box-shadow: 0 12px 40px rgba(0,64,100,.12);
        animation: fadeInUp 0.8s ease-out 0.2s both;
      }}
      .ro-questions-title {{
        color: {NARANJA};
        font-size: 22px;
        font-weight: 900;
        margin: 0 0 18px 0;
        display: flex;
        align-items: center;
        gap: 10px;
      }}
      .ro-questions {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
      }}
      .ro-question {{
        background: rgba(255,255,255,.95);
        border: none;
        border-radius: 14px;
        padding: 20px 18px;
        min-height: 140px;
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
      }}
      .ro-question::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, {NARANJA}, #FF8F5C);
        opacity: 0;
        transition: opacity 0.3s ease;
      }}
      .ro-question:hover {{
        transform: translateY(-6px);
        box-shadow: 0 16px 40px rgba(0,64,100,.15);
      }}
      .ro-question:hover::before {{ opacity: 1; }}
      .ro-question.q5 {{
        grid-column: 1 / -1;
        min-height: auto;
        display: flex;
        align-items: center;
        gap: 20px;
      }}
      .ro-question-icon {{
        font-size: 28px;
        margin-bottom: 10px;
        display: block;
      }}
      .ro-question-title {{
        color: #0E0E0E;
        font-size: 15px;
        line-height: 1.3;
        font-weight: 800;
        margin-bottom: 8px;
      }}
      .ro-question-title b {{
        color: {NARANJA};
        font-size: 18px;
      }}
      .ro-question-copy {{
        color: #444;
        font-size: 13px;
        line-height: 1.5;
      }}
      .ro-route {{
        background: {MORADO};
        color: #fff;
        border-radius: 12px;
        padding: 14px 18px;
        margin-top: 14px;
        font-size: 13px;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 10px;
        box-shadow: 0 4px 15px rgba(34,38,93,0.2);
      }}

      div[data-testid="stRadio"] > div {{
        background: #fff;
        border: 2px solid {BORDE};
        border-radius: 16px;
        padding: 6px;
        gap: 6px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.04);
      }}
      div[data-testid="stRadio"] label {{
        background: transparent;
        border-radius: 12px;
        padding: 10px 16px !important;
        min-height: 44px;
        font-weight: 700;
        font-size: 13.5px;
        transition: all 0.3s ease;
        border: 2px solid transparent;
      }}
      div[data-testid="stRadio"] label:hover {{
        background: {LILA};
        transform: translateY(-1px);
      }}
      div[data-testid="stRadio"] label:has(input:checked) {{
        background: linear-gradient(135deg, {AZUL}, {MORADO});
        color: #fff;
        box-shadow: 0 6px 20px rgba(0,64,100,0.25);
        border-color: transparent;
      }}
      div[data-testid="stRadio"] label:has(input:checked) p {{ color: #fff !important; }}

      .ro-step {{ margin: 24px 0 16px 0; animation: fadeInUp 0.6s ease-out; }}
      .ro-step.light {{ background: transparent; padding: 0; }}
      .ro-step.dark {{
        background: linear-gradient(135deg, {AZUL} 0%, {MORADO} 100%);
        padding: 28px 30px;
        border-radius: 18px;
        box-shadow: 0 12px 40px rgba(0,64,100,.15);
      }}
      .ro-step-tag {{
        display: inline-block;
        background: {LILA};
        color: {MORADO};
        border-radius: 8px;
        padding: 5px 12px;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: .06em;
        text-transform: uppercase;
      }}
      .ro-step.dark .ro-step-tag {{ background: rgba(255,255,255,.15); color: #fff; }}
      .ro-step-title {{
        font-size: 32px;
        line-height: 1.08;
        font-weight: 900;
        color: {AZUL};
        margin: 10px 0 8px 0;
        letter-spacing: -.035em;
      }}
      .ro-step.dark .ro-step-title {{ color: #fff; text-shadow: 0 2px 10px rgba(0,0,0,0.2); }}
      .ro-step-sub {{
        font-size: 15px;
        color: {APAGADO};
        max-width: 980px;
        line-height: 1.5;
      }}
      .ro-step.dark .ro-step-sub {{ color: #C8D9E4; }}

      .ro-filter-title {{
        background: linear-gradient(90deg, {LILA}, #E8E9F5);
        color: {MORADO};
        border-radius: 10px;
        padding: 12px 16px;
        font-size: 13px;
        font-weight: 800;
        margin: 4px 0 8px 0;
        display: flex;
        align-items: center;
        gap: 8px;
        box-shadow: 0 2px 8px rgba(34,38,93,0.06);
      }}
      div[data-testid="stHorizontalBlock"] {{ align-items: flex-start; }}
      div[data-testid="stSelectbox"] label p,
      div[data-testid="stMultiSelect"] label p,
      div[data-testid="stSlider"] label p,
      div[data-testid="stTextInput"] label p {{
        min-height: 34px;
        display: flex;
        align-items: flex-end;
        line-height: 1.25;
        margin-bottom: 2px;
        font-weight: 600 !important;
        color: {TINTA} !important;
      }}
      div[data-testid="stCheckbox"] label p {{ min-height: 0; display: inline; }}

      .ro-kpi-grid {{
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 14px;
        margin: 16px 0 20px 0;
      }}
      .ro-kpi {{
        background: #fff;
        border: 1px solid {BORDE};
        border-radius: 16px;
        padding: 20px 18px;
        min-height: 130px;
        box-shadow: 0 4px 20px rgba(31,53,72,.04);
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
        animation: fadeInUp 0.6s ease-out;
      }}
      .ro-kpi::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        transition: height 0.3s ease;
      }}
      .ro-kpi.orange::before {{ background: linear-gradient(90deg, {NARANJA}, #FF8F5C); }}
      .ro-kpi.blue::before {{ background: linear-gradient(90deg, {AZUL}, #0068A5); }}
      .ro-kpi.purple::before {{ background: linear-gradient(90deg, {MORADO}, #3D4280); }}
      .ro-kpi.green::before {{ background: linear-gradient(90deg, {VERDE}, #4DB87A); }}
      .ro-kpi:hover {{
        transform: translateY(-5px);
        box-shadow: 0 16px 45px rgba(0,64,100,.12);
      }}
      .ro-kpi:hover::before {{ height: 5px; }}
      .ro-kpi-icon {{
        font-size: 22px;
        margin-bottom: 8px;
        display: block;
      }}
      .ro-kpi-label {{
        color: {APAGADO};
        font-size: 10.5px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: .06em;
        line-height: 1.3;
      }}
      .ro-kpi-value {{
        color: {AZUL};
        font-size: 36px;
        line-height: 1.0;
        font-weight: 900;
        margin: 10px 0 6px 0;
        letter-spacing: -.04em;
      }}
      .ro-kpi-note {{
        color: {APAGADO};
        font-size: 11.5px;
        line-height: 1.35;
      }}

      .ro-focus-head {{
        background: linear-gradient(135deg, #fff 0%, #FAFBFF 100%);
        border: 2px solid {BORDE};
        border-radius: 16px;
        padding: 20px 24px;
        margin: 6px 0 14px 0;
        display: flex;
        align-items: center;
        gap: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.04);
        animation: fadeInUp 0.5s ease-out;
      }}
      .ro-focus-name {{
        color: {AZUL};
        font-size: 22px;
        font-weight: 900;
        line-height: 1.2;
      }}
      .ro-index {{
        margin-left: auto;
        background: linear-gradient(135deg, {NARANJA}, #FF8F5C);
        color: #fff;
        border-radius: 14px;
        padding: 12px 18px;
        text-align: center;
        min-width: 100px;
        box-shadow: 0 8px 25px rgba(255,107,43,0.25);
        animation: pulse 2s ease-in-out infinite;
      }}
      .ro-index small {{
        display: block;
        font-size: 9px;
        font-weight: 800;
        opacity: .9;
        letter-spacing: .08em;
        text-transform: uppercase;
      }}
      .ro-index strong {{
        font-size: 28px;
        line-height: 1;
        font-weight: 900;
      }}
      .ro-answer-grid {{
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 12px;
        margin: 0 0 20px 0;
      }}
      .ro-answer {{
        background: linear-gradient(145deg, {LILA}, #E8E9F5);
        border-radius: 14px;
        padding: 18px 16px;
        min-height: 140px;
        transition: all 0.35s ease;
        position: relative;
        overflow: hidden;
        animation: fadeInUp 0.5s ease-out;
      }}
      .ro-answer:hover {{
        transform: translateY(-4px);
        box-shadow: 0 12px 35px rgba(34,38,93,0.1);
      }}
      .ro-answer::after {{
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, {NARANJA}, transparent);
        opacity: 0.5;
      }}
      .ro-answer-q {{
        color: {NARANJA};
        font-weight: 900;
        font-size: 13px;
        letter-spacing: .04em;
      }}
      .ro-answer-title {{
        color: #111;
        font-weight: 800;
        font-size: 12.5px;
        line-height: 1.3;
        margin-top: 4px;
        min-height: 32px;
      }}
      .ro-answer-value {{
        color: {AZUL};
        font-weight: 900;
        font-size: 34px;
        line-height: 1;
        margin: 12px 0 8px 0;
        letter-spacing: -.04em;
      }}
      .ro-answer-note {{
        color: #444;
        font-size: 11.5px;
        line-height: 1.3;
      }}
      .ro-answer.clickable {{
        border: 2px dashed rgba(255,107,43,.55);
        cursor: pointer;
      }}
      .ro-answer-cta {{
        display: inline-block;
        margin-top: 8px;
        background: {NARANJA};
        color: #fff;
        font-size: 10px;
        font-weight: 800;
        letter-spacing: .05em;
        text-transform: uppercase;
        border-radius: 20px;
        padding: 3px 10px;
      }}

      .ro-reading {{
        background: linear-gradient(145deg, {AZUL}, #0a3050);
        border-radius: 16px;
        padding: 24px;
        color: #fff;
        margin-bottom: 16px;
        box-shadow: 0 8px 30px rgba(0,64,100,.15);
        animation: fadeInUp 0.5s ease-out;
      }}
      .ro-reading h4 {{
        color: #fff;
        font-size: 20px;
        margin: 0 0 14px 0;
        font-weight: 800;
      }}
      .ro-reading p {{
        color: #C8D9E4;
        font-size: 13.5px;
        line-height: 1.6;
        margin: 0 0 10px 0;
      }}
      .ro-reading strong {{ color: {NARANJA}; }}

      .ro-q {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: linear-gradient(135deg, {AZUL}, {MORADO});
        color: #fff;
        border-radius: 12px;
        padding: 5px 12px;
        font-size: 12px;
        font-weight: 800;
        margin-right: 8px;
        box-shadow: 0 4px 12px rgba(0,64,100,0.2);
      }}
      .ro-aviso {{
        background: linear-gradient(135deg, #FFF2E9, #FFF8F3);
        border: 2px solid #F6CEB4;
        border-radius: 14px;
        padding: 16px 18px;
        color: #7A4218;
        font-size: 13.5px;
        line-height: 1.5;
        box-shadow: 0 4px 15px rgba(246,206,180,0.2);
      }}

      .ro-calls {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 16px;
        margin: 14px 0 20px 0;
      }}
      .ro-call {{
        background: linear-gradient(145deg, {AZUL}, #0a3050);
        border: 2px solid rgba(195,206,219,0.3);
        border-left: 6px solid #4950BC;
        border-radius: 14px;
        padding: 22px 20px;
        min-height: 190px;
        transition: all 0.35s ease;
        position: relative;
        overflow: hidden;
        animation: fadeInUp 0.5s ease-out;
      }}
      .ro-call::before {{
        content: '';
        position: absolute;
        top: 0;
        right: 0;
        width: 120px;
        height: 120px;
        background: radial-gradient(circle, rgba(255,107,43,0.08) 0%, transparent 70%);
        border-radius: 50%;
      }}
      .ro-call.urgent {{
        border-left-color: {NARANJA};
        animation: pulse 3s ease-in-out infinite;
      }}
      .ro-call.urgent::before {{
        background: radial-gradient(circle, rgba(255,107,43,0.15) 0%, transparent 70%);
      }}
      .ro-call:hover {{
        transform: translateY(-5px);
        box-shadow: 0 16px 45px rgba(0,64,100,.18);
        border-color: rgba(255,107,43,0.3);
      }}
      .ro-call-title {{
        color: #fff;
        font-size: 16px;
        font-weight: 800;
        line-height: 1.35;
        min-height: 65px;
        position: relative;
        z-index: 1;
      }}
      .ro-call-value {{
        color: {NARANJA};
        font-size: 30px;
        font-weight: 900;
        margin: 10px 0 10px;
        position: relative;
        z-index: 1;
        text-shadow: 0 2px 10px rgba(255,107,43,0.2);
      }}
      .ro-call-note {{
        color: #B8C9D8;
        font-size: 12.5px;
        line-height: 1.5;
        position: relative;
        z-index: 1;
      }}

      .ro-call-link {{ text-decoration: none; display: block; }}
      .ro-call-cta {{
        margin-top: 12px;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: .04em;
        text-transform: uppercase;
        color: {NARANJA};
        position: relative;
        z-index: 1;
      }}
      /* Deja aire sobre el llamado al que se salta. */
      .ro-ancla {{ scroll-margin-top: 90px; }}

      .ro-formal-grid {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
        margin: 16px 0 20px 0;
      }}
      .ro-formal {{
        background: linear-gradient(145deg, {LILA}, #E8E9F5);
        border: 1px solid {BORDE};
        border-radius: 14px;
        padding: 20px 18px;
        min-height: 120px;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
        animation: fadeInUp 0.5s ease-out;
      }}
      .ro-formal:hover {{
        transform: translateY(-4px);
        box-shadow: 0 12px 35px rgba(34,38,93,0.1);
      }}
      .ro-formal::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
        background: linear-gradient(180deg, {NARANJA}, {AZUL});
        opacity: 0;
        transition: opacity 0.3s ease;
      }}
      .ro-formal:hover::before {{ opacity: 1; }}
      .ro-formal-title {{
        color: #171717;
        font-size: 16px;
        font-weight: 850;
        margin-bottom: 10px;
        line-height: 1.3;
      }}
      .ro-formal-title b {{
        color: {NARANJA};
        font-size: 20px;
      }}
      .ro-formal-copy {{
        color: #444;
        font-size: 12.5px;
        line-height: 1.45;
      }}

      div[data-testid="stMetric"] {{
        background: linear-gradient(145deg, #fff, #FAFBFF);
        border: 2px solid {BORDE};
        border-radius: 14px;
        padding: 14px 16px;
        min-height: 100px;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0,0,0,0.03);
      }}
      div[data-testid="stMetric"]:hover {{
        transform: translateY(-3px);
        box-shadow: 0 10px 30px rgba(0,0,0,0.06);
      }}
      div[data-testid="stMetricValue"] {{
        font-size: 32px;
        color: {AZUL};
        font-weight: 900;
        letter-spacing: -.02em;
      }}
      div[data-testid="stMetricLabel"] {{
        min-height: 36px;
        color: {APAGADO};
        font-weight: 700;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: .04em;
      }}
      div[data-testid="stDataFrame"] {{
        border: 2px solid {BORDE};
        border-radius: 14px;
        overflow: hidden;
        box-shadow: 0 4px 15px rgba(0,0,0,0.03);
      }}
      div[data-testid="stExpander"] {{
        border: 2px solid {BORDE};
        border-radius: 12px;
        background: #fff;
        box-shadow: 0 4px 15px rgba(0,0,0,0.03);
        transition: all 0.3s ease;
      }}
      div[data-testid="stExpander"]:hover {{
        box-shadow: 0 8px 25px rgba(0,0,0,0.06);
      }}
      div[data-testid="stVerticalBlockBorderWrapper"] {{
        border-color: {BORDE} !important;
        border-radius: 14px;
      }}

      /* El gradiente, el padding y la sombra van solo en el elemento botón.
         Si también los reciben sus hijos (el div y el <p> internos de
         Streamlit), se dibujan cajas anidadas y el botón crece de alto. */
      .stButton > button[kind="primary"],
      div[data-testid="stButton"] button[data-testid="stBaseButton-primary"] {{
        background: linear-gradient(135deg, {NARANJA}, #FF8F5C) !important;
        border: none !important;
        color: #fff !important;
        font-weight: 800 !important;
        border-radius: 12px !important;
        padding: 0 20px !important;
        min-height: 42px !important;
        height: 42px !important;
        line-height: 1.2 !important;
        box-shadow: 0 6px 20px rgba(255,107,43,0.3) !important;
        transition: all 0.3s ease !important;
      }}
      .stButton > button[kind="primary"] *,
      div[data-testid="stButton"] button[data-testid="stBaseButton-primary"] * {{
        background: transparent !important;
        box-shadow: none !important;
        border: none !important;
        color: #fff !important;
        font-weight: 800 !important;
        padding: 0 !important;
        margin: 0 !important;
        min-height: 0 !important;
        line-height: 1.2 !important;
      }}
      .stButton > button[kind="primary"]:hover,
      div[data-testid="stButton"] button[data-testid="stBaseButton-primary"]:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 10px 30px rgba(255,107,43,0.4) !important;
      }}
      .stLinkButton > a[kind="primary"],
      div[data-testid="stLinkButton"] a[data-testid="stBaseLinkButton-primary"] {{
        background: linear-gradient(135deg, {NARANJA}, #FF8F5C) !important;
        border: none !important;
        color: #fff !important;
        font-weight: 800 !important;
        border-radius: 12px !important;
        padding: 0 20px !important;
        min-height: 42px !important;
        height: 42px !important;
        line-height: 1.2 !important;
        box-shadow: 0 6px 20px rgba(255,107,43,0.3) !important;
      }}
      .stLinkButton > a[kind="primary"] *,
      div[data-testid="stLinkButton"] a[data-testid="stBaseLinkButton-primary"] * {{
        background: transparent !important;
        box-shadow: none !important;
        border: none !important;
        color: #fff !important;
        font-weight: 800 !important;
        padding: 0 !important;
        margin: 0 !important;
        min-height: 0 !important;
        line-height: 1.2 !important;
      }}
      .stButton > button[kind="secondary"] {{
        border: 2px solid {AZUL};
        color: {AZUL};
        font-weight: 750;
        border-radius: 12px;
        padding: 0 20px;
        min-height: 42px;
        height: 42px;
        line-height: 1.2;
        transition: all 0.3s ease;
      }}
      .stButton > button[kind="secondary"] * {{
        padding: 0 !important;
        margin: 0 !important;
        min-height: 0 !important;
        line-height: 1.2 !important;
      }}
      .stButton > button[kind="secondary"]:hover {{
        background: {LILA};
        transform: translateY(-2px);
      }}

      /* Los botones de las tarjetas viven en una columna angosta. Sin esto,
         una etiqueta larga desborda la caja de 42px de alto. */
      div[data-testid="stButton"] button p {{
        font-size: 12.5px !important;
        line-height: 1.15 !important;
        white-space: normal !important;
        overflow-wrap: anywhere;
      }}

      abbr.ro-abbr {{
        text-decoration: none;
        border-bottom: 1px dotted currentColor;
        cursor: help;
        font-weight: 800;
      }}
      .ro-period {{
        background: linear-gradient(145deg, #fff, #FAFBFF);
        border: 2px solid {BORDE};
        border-radius: 14px;
        padding: 16px 18px;
        margin: 10px 0 16px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.03);
        transition: all 0.3s ease;
      }}
      .ro-period:hover {{ box-shadow: 0 8px 25px rgba(0,0,0,0.06); }}
      .ro-period-title {{
        color: {AZUL};
        font-size: 15px;
        font-weight: 850;
        margin-bottom: 4px;
      }}
      .ro-period-copy {{
        color: {APAGADO};
        font-size: 12.5px;
        line-height: 1.45;
      }}
      .ro-index-help {{
        background: linear-gradient(145deg, #FFF2E9, #FFF8F3);
        border: 2px solid #F6CEB4;
        border-radius: 16px;
        padding: 22px 24px;
        margin: 14px 0 18px 0;
        box-shadow: 0 6px 20px rgba(246,206,180,0.15);
        animation: fadeInUp 0.5s ease-out;
      }}
      .ro-index-help h4 {{
        margin: 0 0 10px 0;
        color: {AZUL};
        font-size: 19px;
        font-weight: 800;
      }}
      .ro-index-help p {{
        margin: 6px 0;
        color: #4B4B4B;
        font-size: 13px;
        line-height: 1.5;
      }}
      .ro-index-help strong {{ color: {NARANJA}; }}
      .ro-glossary {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
        margin: 10px 0 16px 0;
      }}
      .ro-glossary-item {{
        background: linear-gradient(145deg, #fff, #FAFBFF);
        border: 2px solid {BORDE};
        border-radius: 12px;
        padding: 14px 16px;
        transition: all 0.3s ease;
      }}
      .ro-glossary-item:hover {{
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.06);
        border-color: {NARANJA};
      }}
      .ro-glossary-item b {{ color: {AZUL}; font-size: 14px; }}
      .ro-glossary-item span {{ color: {APAGADO}; font-size: 12px; }}

      .ro-divider {{
        height: 2px;
        background: linear-gradient(90deg, transparent, {BORDE}, transparent);
        margin: 24px 0;
        border: none;
      }}
      .ro-urgent-badge {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: linear-gradient(135deg, {NARANJA}, #FF8F5C);
        color: #fff;
        font-size: 10px;
        font-weight: 800;
        padding: 4px 10px;
        border-radius: 20px;
        text-transform: uppercase;
        letter-spacing: .06em;
        animation: pulse 2s ease-in-out infinite;
      }}

      .ro-prov-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
        margin: 8px 0 14px 0;
      }}
      .ro-prov {{
        background: linear-gradient(145deg, #fff, #FAFBFF);
        border: 1px solid {BORDE};
        border-left: 5px solid {VERDE};
        border-radius: 12px;
        padding: 12px 14px;
        transition: all 0.3s ease;
      }}
      .ro-prov.baja {{ border-left-color: {GRIS}; opacity: .92; }}
      .ro-prov:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 22px rgba(0,64,100,.08);
      }}
      .ro-prov-nombre {{
        color: {AZUL};
        font-size: 13.5px;
        font-weight: 850;
        line-height: 1.3;
      }}
      .ro-prov-meta {{
        color: {APAGADO};
        font-size: 11.5px;
        margin-top: 5px;
        line-height: 1.4;
      }}
      .ro-prov-estado {{
        display: inline-block;
        border-radius: 20px;
        padding: 2px 9px;
        font-size: 10px;
        font-weight: 800;
        letter-spacing: .04em;
        text-transform: uppercase;
        margin-top: 6px;
      }}
      .ro-prov-estado.si {{ background: rgba(47,158,101,.14); color: {VERDE}; }}
      .ro-prov-estado.no {{ background: rgba(134,154,180,.18); color: #4A5B70; }}

      ::-webkit-scrollbar {{ width: 8px; }}
      ::-webkit-scrollbar-track {{ background: {FONDO}; }}
      ::-webkit-scrollbar-thumb {{ background: {BORDE}; border-radius: 4px; }}
      ::-webkit-scrollbar-thumb:hover {{ background: {APAGADO}; }}

      @media (max-width: 980px) {{
        .ro-questions {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        .ro-kpi-grid, .ro-answer-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        .ro-calls {{ grid-template-columns: 1fr; }}
        .ro-formal-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        .ro-prov-grid {{ grid-template-columns: 1fr; }}
        .ro-hero {{ align-items: flex-start; flex-direction: column; }}
        .ro-hero-meta {{ margin-left: 0; justify-content: flex-start; max-width: none; }}
        .ro-hero-title {{ font-size: 26px; }}
      }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------
# Columnas que la app realmente usa de cada parquet. Leer solo estas (y
# compactar los textos repetidos a dtype category) reduce la memoria del
# proceso a menos de la mitad, necesario para el límite del hosting gratuito.
_COLUMNAS_APP = {
    "ocds_procesos": [
        "ocid", "fecha", "entidad", "metodo_contratacion", "tipo_objeto",
        "cubso_descripcion", "monto_adjudicado", "proveedor_id",
        "proveedor_nombre", "anio",
    ],
    "documentos_convocatoria": [
        "ocid", "tipo_documento", "titulo", "formato", "url",
        "fecha_publicacion",
    ],
    "convocatorias_vigentes": [
        "ocid", "convocatoria", "titulo", "descripcion", "entidad",
        "metodo_contratacion", "tipo_objeto", "monto_referencial",
        "fecha_publicacion", "fecha_inicio_ofertas", "fecha_cierre_ofertas",
        "cubso_descripcion", "n_documentos", "origen_limite",
        "dias_para_cierre", "vigencia",
    ],
    "proveedores_padron": [
        "ruc", "razon_social", "es_habilitado", "es_apto_contratar",
        "estado_habilitacion", "capitulos_nombres", "fecha_consulta",
    ],
}


@st.cache_data(max_entries=10)
def cargar(ruta):
    """Lee un Parquet si existe; devuelve None si la etapa no se corrió.

    Optimización de memoria: lee solo las columnas que la app usa y convierte
    a category los textos de baja cardinalidad (excepto fechas).
    """
    if not ruta.exists():
        return None
    import pyarrow.parquet as _pq

    deseadas = _COLUMNAS_APP.get(ruta.stem)
    columnas = None
    if deseadas:
        disponibles = set(_pq.read_schema(ruta).names)
        columnas = [c for c in deseadas if c in disponibles] or None
    df = pd.read_parquet(ruta, columns=columnas)
    for c in df.columns:
        if "fecha" in c:
            continue
        if str(df[c].dtype) in ("object", "str"):
            n = df[c].nunique(dropna=True)
            if 0 < n and n / max(len(df), 1) < 0.5:
                df[c] = df[c].astype("category")
    return df


maestro = cargar(config.PARQUET_MAESTRO)
ocds = cargar(config.PARQUET_OCDS)
padron = cargar(config.PARQUET_PADRON)
convocatorias = cargar(config.PARQUET_CONVOCATORIAS)
documentos = cargar(config.PARQUET_DOCUMENTOS)
cronograma = cargar(config.PARQUET_CRONOGRAMA)
estacionalidad = cargar(config.PARQUET_ESTACIONALIDAD)

# Índice de documentos por llamado. Permite (1) marcar en la lista qué
# convocatorias sí traen bases publicadas y (2) ofrecer un caso real cuando
# el llamado elegido no tiene documentos en la fuente consultada.
if documentos is not None and not documentos.empty and "ocid" in documentos.columns:
    DOCS_POR_OCID = documentos.groupby(documentos["ocid"].astype(str)).size()
    _bases = documentos[
        documentos["tipo_documento"].astype(str) == "biddingDocuments"
    ]
    BASES_POR_OCID = (
        _bases.groupby(_bases["ocid"].astype(str)).size()
        if not _bases.empty else pd.Series(dtype="int64")
    )
else:
    DOCS_POR_OCID = pd.Series(dtype="int64")
    BASES_POR_OCID = pd.Series(dtype="int64")
OCIDS_CON_DOCUMENTOS = set(DOCS_POR_OCID.index)

# Última actividad real del snapshot de convocatorias.
#
# Se usa fecha_inicio_ofertas (tenderPeriod.startDate del OCDS) y NO
# fecha_publicacion. Motivo medido sobre los datos: fecha_publicacion viene del
# timestamp del release, es decir del momento en que el pipeline del OECE
# escribió el registro, no de cuándo se convocó el procedimiento. Ese campo
# concentra miles de registros en domingos y trae procesos de 2014 fechados en
# 2026. fecha_inicio_ofertas, en cambio, reproduce el calendario administrativo:
# entre 260 y 372 convocatorias por día hábil, cero en fines de semana y
# feriados. Cobertura del campo: 92,9% de las filas.
COLUMNA_FECHA_CONVOCATORIA = "fecha_inicio_ofertas"

if convocatorias is not None and not convocatorias.empty:
    _columna_actividad = (
        COLUMNA_FECHA_CONVOCATORIA
        if COLUMNA_FECHA_CONVOCATORIA in convocatorias.columns
        else ("fecha_publicacion" if "fecha_publicacion" in convocatorias.columns else None)
    )
else:
    _columna_actividad = None

if _columna_actividad:
    _fecha_conv_snapshot = pd.to_datetime(
        convocatorias[_columna_actividad], errors="coerce", utc=True
    )
    _sin_fecha_convocatoria = int(_fecha_conv_snapshot.isna().sum())
    if _fecha_conv_snapshot.notna().any():
        _ultimo_dia_snapshot = _fecha_conv_snapshot.max().normalize()
        _mask_ultimo_dia = _fecha_conv_snapshot.dt.normalize().eq(_ultimo_dia_snapshot)
        _ultimos_snapshot = convocatorias.loc[_mask_ultimo_dia].copy()
        ultimos_procedimientos_snapshot = (
            _ultimos_snapshot["ocid"].nunique()
            if "ocid" in _ultimos_snapshot.columns
            else len(_ultimos_snapshot)
        )
        ultima_fecha_snapshot_txt = _ultimo_dia_snapshot.strftime("%d/%m/%Y")
        categorias_ultima_publicacion = set(
            _ultimos_snapshot.get("cubso_descripcion", pd.Series(dtype="object"))
            .dropna().astype(str)
        )
    else:
        ultimos_procedimientos_snapshot = 0
        ultima_fecha_snapshot_txt = "No disponible"
        categorias_ultima_publicacion = set()
else:
    _sin_fecha_convocatoria = 0
    ultimos_procedimientos_snapshot = 0
    ultima_fecha_snapshot_txt = "No disponible"
    categorias_ultima_publicacion = set()

if maestro is None:
    st.error("Falta el dataset maestro. Ejecute `python diagnostico.py` después de la ingesta.")
    st.stop()

for clave, valor in {
    "pantalla": "1 · ¿Dónde me conviene buscar?",
    "categoria": None,
    "ocid": None,
    "ocid_checklist": None,
    "listos": set(),
}.items():
    st.session_state.setdefault(clave, valor)
    # Reasignación deliberada: Streamlit elimina el estado de los widgets que
    # no se renderizan en la corrida actual. "categoria" es la clave de un
    # selectbox del Paso 1; al navegar al Paso 2 ese widget no existe y su
    # estado se borraría en el primer rerun, deshabilitando el filtro de
    # categoría exacta. Volver a escribir la clave en cada corrida la marca
    # como estado de la app y evita esa limpieza.
    st.session_state[clave] = st.session_state[clave]


# ---------------------------------------------------------------------------
# Helpers de presentación
# ---------------------------------------------------------------------------
def numero_seguro(x, default=0.0) -> float:
    try:
        if pd.isna(x):
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def normalizar_busqueda(valor) -> str:
    """Normaliza texto para que la búsqueda ignore mayúsculas y tildes.

    Ejemplo:
        'alimentación' y 'ALIMENTACION' se comparan como 'alimentacion'.
    """
    if valor is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.casefold().strip()


def _patron_clave(clave: str) -> str:
    """Convierte una palabra clave del rubro en una expresión regular segura.

    Toda clave se ancla al inicio de palabra (\\b). Sin ese ancla, 'racion'
    hacía match dentro de 'elaboracion' y arrastraba consultorías y
    expedientes técnicos al rubro de alimentos.

    Si la clave termina en '$', además se exige fin de palabra admitiendo
    plural: 'carne$' acepta carne y carnes, pero no carnet.
    """
    exacto = clave.endswith("$")
    base = clave[:-1] if exacto else clave
    patron = r"\b" + re.escape(base.strip())
    if exacto:
        patron += r"(?:es|s)?\b"
    return patron


def mascara_rubros(descripciones: pd.Series, rubros: list[str]) -> pd.Series:
    """Devuelve una máscara booleana con las categorías del rubro elegido.

    Se compara la descripción CUBSO normalizada contra las palabras clave
    del rubro. Al ser un único patrón regex, la comparación es vectorizada
    y no recorre el DataFrame fila por fila.
    """
    if not rubros:
        return pd.Series(True, index=descripciones.index)
    claves = sorted({clave for r in rubros for clave in RUBROS_NEGOCIO.get(r, [])})
    if not claves:
        return pd.Series(True, index=descripciones.index)
    patron = "|".join(_patron_clave(clave) for clave in claves)
    normalizadas = descripciones.astype(str).map(normalizar_busqueda)
    return normalizadas.str.contains(patron, na=False, regex=True)


def texto_seguro(x) -> str:
    if x is None:
        return "—"
    try:
        if pd.isna(x):
            return "—"
    except (TypeError, ValueError):
        pass
    return escape(str(x))


def formato_soles(x) -> str:
    """Formatea montos para lectura ejecutiva, sin esconder su magnitud."""
    x = numero_seguro(x)
    if abs(x) >= 1_000_000_000:
        return f"{MONEDA} {x/1_000_000_000:,.1f} MM"
    if abs(x) >= 1_000_000:
        return f"{MONEDA} {x/1_000_000:,.1f} M"
    if abs(x) >= 1_000:
        return f"{MONEDA} {x/1_000:,.0f} K"
    return f"{MONEDA} {x:,.0f}"


def monto_declarado(fila) -> tuple[str, str]:
    """Devuelve (texto, nota) para el monto de un llamado.

    El publicador escribe value.amount = 0 de forma deliberada cuando la
    informacion del procedimiento esta reservada por ley (bandera
    hasTenderInformationProtectedByLaw del OCDS). Sobre la ultima descarga, dos
    de cada tres montos ausentes corresponden a ese caso. Imprimir "S/ 0"
    afirma que el contrato no vale nada, que es la unica de las tres lecturas
    posibles que es falsa: se declara el estado en vez de inventar una cifra.
    """
    monto = numero_seguro(fila.get("monto_referencial"))
    if monto > 0:
        return formato_soles(monto), f"{monto / config.UIT_SOLES:,.0f} {sigla('UIT')}"
    try:
        reservada = bool(fila.get("info_reservada"))
    except (TypeError, ValueError):
        reservada = False
    if reservada:
        return "Reservado", "Monto reservado por ley"
    return "No publicado", "La entidad no publicó el monto"


def plazo_declarado(dias, origen=None) -> tuple[str, str, bool]:
    """Devuelve (valor, etiqueta, vencido) para el plazo de un llamado.

    Dos precisiones que el numero solo no transmite. Un valor entre 0 y 1 se
    redondeaba a "0 d" y se leia como si aun quedara tiempo, cuando en realidad
    vence hoy; por debajo de cero ya no se puede participar. Y el plazo no
    siempre es el de presentacion de ofertas: cuando el tenderPeriod viene
    colapsado (startDate igual a endDate en casi todos los procesos), el limite
    se toma del cierre de consultas, que es una etapa distinta y asi se rotula.
    """
    etiqueta = "fin de consultas" if origen == "fin de consultas" else "cierre de ofertas"
    if pd.isna(dias):
        return "—", "SIN FECHA PUBLICADA", False
    if dias < 0:
        return "Cerrado", "YA NO PUEDE POSTULAR", True
    if dias < 1:
        return "Hoy", f"ÚLTIMO DÍA · {etiqueta.upper()}", False
    return f"{dias:.0f} d", f"RESTAN · {etiqueta.upper()}", False


def mes_nombre(mes) -> str:
    nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    try:
        if pd.isna(mes):
            return "—"
        n = int(mes)
        return nombres[n - 1] if 1 <= n <= 12 else "—"
    except (TypeError, ValueError):
        return "—"



SIGLAS = {
    "MYPE": "Micro y Pequeña Empresa",
    "UIT": "Unidad Impositiva Tributaria",
    "CUBSO": "Catálogo Único de Bienes, Servicios y Obras",
    "OCDS": "Open Contracting Data Standard: estándar de datos de contrataciones abiertas",
    "RNP": "Registro Nacional de Proveedores",
    "OECE": "Organismo Especializado para las Contrataciones Públicas Eficientes",
    "SEACE": "Sistema Electrónico de Contrataciones del Estado",
    "API": "Interfaz que permite consultar información de otro sistema de forma automática",
    "RUC": "Registro Único de Contribuyentes",
}


def sigla(nombre: str) -> str:
    """Devuelve una sigla con explicación al pasar el mouse."""
    detalle = SIGLAS.get(nombre, nombre)
    return (
        f'<abbr class="ro-abbr" title="{escape(detalle, quote=True)}">'
        f'{escape(nombre)}</abbr>'
    )


def etiqueta_competencia(valor) -> str:
    """Traduce las etiquetas técnicas a lenguaje más comercial."""
    mapa = {
        "Sin adjudicatario vigente": "Sin ganador histórico habilitado",
        "Poca competencia (1-2)": "Poca competencia conocida (1-2)",
        "Competencia media (3-5)": "Competencia media (3-5)",
        "Disputado (>5)": "Muy competido (>5)",
        "Competencia no determinada": "Competencia por validar",
    }
    return mapa.get(str(valor), str(valor))


def resumen_periodo(anios: list[int], meses: list[int]) -> str:
    if not anios:
        return "Sin años seleccionados"
    anios_txt = ", ".join(str(a) for a in sorted(anios))
    if len(meses) == 12:
        meses_txt = "todos los meses"
    else:
        meses_txt = ", ".join(mes_nombre(m) for m in sorted(meses))
    return f"{anios_txt} · {meses_txt}"


def ultima_corrida(prefijos: list[str]) -> str:
    """Fecha de la última corrida de un módulo del pipeline.

    Lee primero el metadato versionado (data/processed/metadata_corridas.json),
    que viaja con los parquet en el repositorio y por lo tanto existe también
    en Streamlit Cloud, donde logs/ y reports/ llegan vacíos (.gitignore).
    Los nombres de archivos de logs/reportes quedan como respaldo local para
    corridas anteriores a la introducción del metadato.
    """
    fechas = []
    patron = re.compile(r"(\d{8})_(\d{6})")

    # 1) Metadato versionado: la fuente que funciona en cualquier entorno.
    ruta_meta = getattr(config, "RUTA_METADATA_CORRIDAS", None)
    if ruta_meta and Path(ruta_meta).exists():
        try:
            meta = json.loads(Path(ruta_meta).read_text(encoding="utf-8"))
            for prefijo in prefijos:
                valor = meta.get(prefijo)
                if valor:
                    fechas.append(datetime.strptime(valor, "%Y%m%d_%H%M%S"))
        except (json.JSONDecodeError, ValueError, OSError):
            pass

    # 2) Respaldo local: fecha grabada en los nombres de logs/reportes.
    if not fechas:
        carpetas = [getattr(config, "LOG_DIR", None), getattr(config, "REPORT_DIR", None)]
        for carpeta in carpetas:
            if not carpeta:
                continue
            carpeta = Path(carpeta)
            if not carpeta.exists():
                continue
            for prefijo in prefijos:
                for archivo in carpeta.glob(f"{prefijo}_*"):
                    m = patron.search(archivo.name)
                    if not m:
                        continue
                    try:
                        fechas.append(datetime.strptime("".join(m.groups()), "%Y%m%d%H%M%S"))
                    except ValueError:
                        pass

    if not fechas:
        return "No encontrada"
    return max(fechas).strftime("%d/%m/%Y %H:%M")


def filtrar_historico_periodo(df: pd.DataFrame | None, anios: list[int], meses: list[int]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    salida = df.copy()
    salida["fecha"] = pd.to_datetime(salida["fecha"], errors="coerce", utc=True)
    if "anio" not in salida.columns:
        salida["anio"] = salida["fecha"].dt.year
    salida = salida[salida["anio"].isin(anios)]
    salida = salida[salida["fecha"].dt.month.isin(meses)]
    return salida


def construir_maestro_periodo(
    ocds_periodo: pd.DataFrame,
    padron_actual: pd.DataFrame | None,
    convocatorias_actuales: pd.DataFrame | None,
) -> pd.DataFrame:
    """Recalcula las métricas del radar para los años y meses elegidos.

    No modifica los Parquet. Solo reconstruye la vista que consume la app.
    La habilitación del proveedor sigue siendo la del padrón vigente.
    """
    if ocds_periodo is None or ocds_periodo.empty:
        return pd.DataFrame()

    base = ocds_periodo.copy()
    base["fecha"] = pd.to_datetime(base["fecha"], errors="coerce", utc=True)
    base["monto_adjudicado"] = pd.to_numeric(base["monto_adjudicado"], errors="coerce")

    validos = base.dropna(subset=["cubso_descripcion", "monto_adjudicado"])
    demanda = (
        validos.groupby("cubso_descripcion", as_index=False, observed=True)
        .agg(
            demanda_soles=("monto_adjudicado", "sum"),
            n_procesos=("ocid", "nunique"),
        )
    )

    detalle = base.dropna(subset=["cubso_descripcion", "proveedor_id"]).copy()
    adjudicados = (
        detalle.groupby("cubso_descripcion", as_index=False, observed=True)
        .agg(
            densidad_proveedores=("proveedor_id", "nunique"),
            adjudicados=("proveedor_id", "nunique"),
            n_adjudicaciones=("ocid", "size"),
            n_procesos_con_adjudicacion=("ocid", "nunique"),
        )
    )

    if padron_actual is not None and not padron_actual.empty:
        pad = padron_actual.copy()
        if "ruc" not in pad.columns and "proveedor_id" in pad.columns:
            pad["ruc"] = pad["proveedor_id"].astype("string")
        pad["ruc"] = pad["ruc"].astype("string")
        pad = pad.drop_duplicates(subset=["ruc"], keep="last")

        detalle["ruc"] = (
            detalle["proveedor_id"].astype("string")
            .str.extract(r"(\d{11})", expand=False)
        )
        con_ruc = detalle.dropna(subset=["ruc"]).merge(
            pad[["ruc", "es_habilitado", "es_apto_contratar"]],
            on="ruc",
            how="left",
        )
        con_ruc["vigente"] = con_ruc["es_habilitado"].fillna(False)
        con_ruc["apto"] = con_ruc["es_apto_contratar"].fillna(False)

        def contar(mask, nombre):
            datos = con_ruc if mask is None else con_ruc[mask]
            return (
                datos.groupby("cubso_descripcion", observed=True)["ruc"]
                .nunique()
                .rename(nombre)
            )

        vigencia = (
            pd.concat(
                [
                    contar(None, "ganadores_historicos"),
                    contar(con_ruc["vigente"], "competencia_vigente"),
                    contar(con_ruc["apto"], "competencia_apta"),
                ],
                axis=1,
            )
            .fillna(0)
            .astype("int64")
            .reset_index()
        )
        vigencia["salieron_del_registro"] = (
            vigencia["ganadores_historicos"] - vigencia["competencia_vigente"]
        )
        densidad = adjudicados.merge(vigencia, on="cubso_descripcion", how="left")
    else:
        # Fallback: conserva la última foto del maestro si no está disponible el padrón.
        cols = [
            c for c in [
                "cubso_descripcion", "ganadores_historicos", "competencia_vigente",
                "competencia_apta", "salieron_del_registro"
            ] if c in maestro.columns
        ]
        densidad = adjudicados.merge(
            maestro[cols].drop_duplicates("cubso_descripcion"),
            on="cubso_descripcion",
            how="left",
        )

    densidad["mercado_desierto"] = (
        (densidad["competencia_vigente"].fillna(-1) == 0)
        & (densidad["ganadores_historicos"].fillna(0) > 0)
    )

    salida = demanda.merge(densidad, on="cubso_descripcion", how="left")
    salida["ticket_promedio"] = (
        salida["demanda_soles"] / salida["n_procesos"].replace(0, pd.NA)
    )
    salida["concentracion"] = (
        salida["n_procesos"] / salida["densidad_proveedores"].replace(0, pd.NA)
    ).round(2)

    # Llamados: siempre son la foto de la última corrida del monitor.
    if convocatorias_actuales is not None and not convocatorias_actuales.empty:
        vigentes = convocatorias_actuales[
            convocatorias_actuales["vigencia"].isin(["VIGENTE", "POR CERRAR"])
        ]
        por_categoria = (
            vigentes.groupby("cubso_descripcion", as_index=False, observed=True)
            .agg(
                convocatorias_vigentes=("ocid", "nunique"),
                monto_vigente=("monto_referencial", "sum"),
            )
        )
        salida = salida.merge(por_categoria, on="cubso_descripcion", how="left")
    else:
        salida["convocatorias_vigentes"] = 0
        salida["monto_vigente"] = 0

    salida["convocatorias_vigentes"] = (
        salida["convocatorias_vigentes"].fillna(0).astype("Int64")
    )
    salida["accionable_hoy"] = salida["convocatorias_vigentes"] > 0

    # Perfil mensual para el periodo seleccionado.
    temporal = validos.dropna(subset=["fecha"]).copy()
    if not temporal.empty:
        temporal["mes"] = temporal["fecha"].dt.month
        por_mes = (
            temporal.groupby(["cubso_descripcion", "mes"], observed=True)["monto_adjudicado"]
            .sum()
            .reset_index()
        )
        total = por_mes.groupby("cubso_descripcion", observed=True)["monto_adjudicado"].transform("sum")
        por_mes["participacion"] = por_mes["monto_adjudicado"] / total.replace(0, np.nan)
        idx = por_mes.groupby("cubso_descripcion", observed=True)["monto_adjudicado"].idxmax()
        pico = por_mes.loc[idx, ["cubso_descripcion", "mes", "participacion"]].rename(
            columns={"mes": "mes_pico", "participacion": "concentracion_mes"}
        )
        activos = (
            por_mes.groupby("cubso_descripcion", as_index=False, observed=True)
            .agg(meses_activos=("mes", "nunique"))
        )
        salida = salida.merge(pico, on="cubso_descripcion", how="left")
        salida = salida.merge(activos, on="cubso_descripcion", how="left")
    else:
        salida["mes_pico"] = pd.NA
        salida["concentracion_mes"] = pd.NA
        salida["meses_activos"] = pd.NA

    # Ticket y competencia en lenguaje de bandas.
    salida["ticket_uit"] = (salida["ticket_promedio"] / config.UIT_SOLES).round(2)

    competencia = pd.to_numeric(salida["competencia_vigente"], errors="coerce")
    comp_log = np.log1p(competencia)
    if comp_log.notna().any():
        minimo, maximo = comp_log.min(), comp_log.max()
        if pd.notna(minimo) and pd.notna(maximo) and maximo != minimo:
            salida["espacio_mercado"] = (1 - (comp_log - minimo) / (maximo - minimo)).round(4)
        else:
            salida["espacio_mercado"] = np.where(comp_log.notna(), 1.0, np.nan)
    else:
        salida["espacio_mercado"] = np.nan

    sin_cruce = salida["espacio_mercado"].isna()
    if sin_cruce.any():
        conc = pd.to_numeric(salida.loc[sin_cruce, "concentracion"], errors="coerce")
        salida.loc[sin_cruce, "espacio_mercado"] = (
            1 / (1 + conc.fillna(conc.median()))
        ).round(4)

    demanda_uit = salida["demanda_soles"] / config.UIT_SOLES
    salida["apto_para_ranking"] = (
        (salida["n_procesos"] >= config.MINIMO_PROCESOS_MERCADO)
        & (demanda_uit >= config.MINIMO_DEMANDA_UIT_MERCADO)
    )

    salida["banda_ticket"] = pd.cut(
        salida["ticket_uit"],
        bins=config.BANDAS_TICKET_UIT,
        labels=config.BANDAS_TICKET_ETIQUETAS,
        include_lowest=True,
    )
    salida["banda_competencia"] = pd.cut(
        competencia,
        bins=config.BANDAS_COMPETENCIA,
        labels=config.BANDAS_COMPETENCIA_ETIQUETAS,
    ).astype("object")
    salida["banda_competencia"] = salida["banda_competencia"].fillna(
        "Competencia no determinada"
    )

    # Índice: misma metodología del proyecto, recalculada para el periodo.
    salida["demanda_log"] = np.log1p(salida["demanda_soles"].clip(lower=0))
    minimo, maximo = salida["demanda_log"].min(), salida["demanda_log"].max()
    if pd.isna(minimo) or maximo == minimo:
        salida["demanda_escalada"] = 0.5
    else:
        salida["demanda_escalada"] = (
            (salida["demanda_log"] - minimo) / (maximo - minimo)
        ).round(4)

    salida["espacio_escalado"] = salida["espacio_mercado"].clip(0, 1).round(4)
    salida["accesibilidad"] = (
        salida["banda_ticket"].astype("string")
        .map(config.FACTOR_ACCESIBILIDAD)
        .astype("float64")
        .fillna(config.FACTOR_ACCESIBILIDAD_DESCONOCIDO)
    )

    pesos = config.PESOS_INDICE
    potencial = (
        pesos["demanda"] * salida["demanda_escalada"].fillna(0)
        + pesos["espacio"] * salida["espacio_escalado"].fillna(0)
    )
    salida["potencial_mercado"] = (100 * potencial).round(1)
    salida["indice_oportunidad"] = (
        100 * potencial * salida["accesibilidad"]
    ).round(1)

    return salida.sort_values("demanda_soles", ascending=False)


def q(etiqueta: str, texto: str) -> None:
    st.markdown(
        f'<span class="ro-q">{escape(etiqueta)}</span>'
        f'<span style="font-size:13px;color:{APAGADO};font-weight:650">{escape(texto)}</span>',
        unsafe_allow_html=True,
    )


def titulo_paso(etiqueta: str, titulo: str, subtitulo: str, dark: bool = False) -> None:
    clase = "dark" if dark else "light"
    st.markdown(
        f"""
        <div class="ro-step {clase}">
          <span class="ro-step-tag">{escape(etiqueta)}</span>
          <div class="ro-step-title">{escape(titulo)}</div>
          <div class="ro-step-sub">{escape(subtitulo)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_preguntas_negocio() -> None:
    st.markdown(
        f"""
        <div class="ro-questions-wrap">
          <div class="ro-questions-title">🎯 Las 5 preguntas para decidir dónde vale la pena postular</div>
          <div class="ro-questions">
            <div class="ro-question">
              <span class="ro-question-icon">💰</span>
              <div class="ro-question-title"><b>Q1</b> · ¿Dónde compra más el Estado?</div>
              <div class="ro-question-copy">Mira cuánto dinero adjudicó el Estado en cada categoría durante el periodo que elegiste.</div>
            </div>
            <div class="ro-question">
              <span class="ro-question-icon">🛡️</span>
              <div class="ro-question-title"><b>Q2</b> · ¿Dónde tengo menos competencia conocida?</div>
              <div class="ro-question-copy">Cuenta cuántos proveedores que ya ganaron siguen habilitados para volver a competir.</div>
            </div>
            <div class="ro-question">
              <span class="ro-question-icon">📅</span>
              <div class="ro-question-title"><b>Q3</b> · ¿En qué meses se mueve más la compra?</div>
              <div class="ro-question-copy">Ayuda a preparar compras, personal y documentos antes de que aparezcan los llamados.</div>
            </div>
            <div class="ro-question">
              <span class="ro-question-icon">📏</span>
              <div class="ro-question-title"><b>Q4</b> · ¿El tamaño del contrato está a mi alcance?</div>
              <div class="ro-question-copy">Compara el monto promedio con la {sigla("UIT")} para saber si encaja con la capacidad de una {sigla("MYPE")}.</div>
            </div>
            <div class="ro-question q5">
              <span class="ro-question-icon" style="font-size:32px;margin:0">🏁</span>
              <div>
                <div class="ro-question-title"><b>Q5</b> · ¿Cuántos proveedores siguen realmente en carrera?</div>
                <div class="ro-question-copy">Cruza quién ganó antes con quién sigue habilitado hoy en el {sigla("RNP")}.</div>
              </div>
            </div>
          </div>
          <div class="ro-route">
            <span style="font-size:18px">🧭</span>
            <span>Elegir categoría → revisar la oportunidad → validar oportunidades actuales en SEACE → preparar documentos → decidir si postular.</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(items: list[dict]) -> None:
    # Cada KPI lleva un icono asociado a su etiqueta. El diccionario evita
    # repetir el icono en cada llamada y mantiene una sola fuente de verdad.
    icons = {
        "Categorías para revisar": "📊",
        "Q1 · Compras adjudicadas": "💰",
        "Convocatorias del último día registrado": "📡",
        "Q2 · Sin ganador histórico habilitado": "🚨",
        "Mejor índice": "⭐",
        "Llamados abiertos": "📋",
        "Monto referencial total": "💵",
        "Cierran esta semana": "⏰",
        "Entidades comprando": "🏛️",
        "Monto típico": "📐",
        "Última publicación disponible": "📰",
        "Mayor cierre disponible": "🔒",
    }
    cards = []
    for item in items:
        icon = icons.get(item.get("label", ""), "📈")
        cards.append(
            f'<div class="ro-kpi {item.get("accent", "blue")}">'
            f'<span class="ro-kpi-icon">{icon}</span>'
            f'<div class="ro-kpi-label">{escape(str(item["label"]))}</div>'
            f'<div class="ro-kpi-value">{escape(str(item["value"]))}</div>'
            f'<div class="ro-kpi-note">{escape(str(item.get("note", "")))}</div>'
            '</div>'
        )
    st.markdown(
        '<div class="ro-kpi-grid">' + ''.join(cards) + '</div>',
        unsafe_allow_html=True,
    )


def render_respuestas_categoria(fila: pd.Series, est_foco: pd.Series | None) -> None:
    demanda = formato_soles(fila.get("demanda_soles"))
    vigentes = int(round(numero_seguro(fila.get("competencia_vigente"))))
    ganaron = int(round(numero_seguro(fila.get("ganadores_historicos"))))
    ticket_uit = numero_seguro(fila.get("ticket_uit"))
    banda = etiqueta_competencia(fila.get("banda_competencia"))
    banda_ticket = texto_seguro(fila.get("banda_ticket"))

    mes = fila.get("mes_pico")
    concentracion = None
    if est_foco is not None:
        mes = est_foco.get("mes_pico", mes)
        concentracion = est_foco.get("concentracion_mes")
    mes_txt = mes_nombre(mes)
    if concentracion is not None and pd.notna(concentracion):
        nota_q3 = f"Mes pico · {numero_seguro(concentracion) * 100:.0f}% de concentración"
    else:
        nota_q3 = "Mes pico de la categoría"

    q_icons = {"Q1": "💰", "Q2": "🛡️", "Q3": "📅", "Q4": "📏", "Q5": "🏁"}
    cards = [
        ("Q1", "Cuánto compró el Estado", demanda, "Monto adjudicado en el periodo elegido"),
        ("Q2", "Competidores conocidos habilitados", f"{vigentes}", banda),
        ("Q3", "Mes con más compras", mes_txt, nota_q3),
        ("Q4", "Tamaño promedio del contrato", f'{ticket_uit:.1f} {sigla("UIT")}', banda_ticket),
        ("Q5", "Ganaron antes → siguen habilitados", f"{ganaron} → {vigentes}", "Histórico seleccionado → estado actual"),
    ]
    # Q2 y Q5 son las tarjetas que tienen detalle nominal: el botón que abre el
    # popup se dibuja justo debajo de la grilla, así que se marcan visualmente.
    con_detalle = {"Q2", "Q5"}
    html = []
    for qq, titulo, valor, nota in cards:
        icon = q_icons.get(qq, "📊")
        clase = "ro-answer clickable" if qq in con_detalle else "ro-answer"
        cta = (
            '<span class="ro-answer-cta">Ver nombres ↓</span>'
            if qq in con_detalle else ""
        )
        html.append(
            f'<div class="{clase}">'
            f'<div class="ro-answer-q">{icon} {qq}</div>'
            f'<div class="ro-answer-title">{escape(titulo)}</div>'
            f'<div class="ro-answer-value">{str(valor) if qq == "Q4" else escape(str(valor))}</div>'
            f'<div class="ro-answer-note">{escape(str(nota))}</div>'
            f'{cta}'
            '</div>'
        )
    st.markdown(
        '<div class="ro-answer-grid">' + ''.join(html) + '</div>',
        unsafe_allow_html=True,
    )


def render_historial_rubro(df: pd.DataFrame, rubros: list[str]) -> None:
    """Llamados ya cerrados del rubro, con el detalle de lo que pidieron.

    Los vigentes dicen qué se puede postular hoy; son pocos y dependen del
    desfase de la fuente. Los cerrados son el material de estudio: qué compró
    cada entidad, con qué procedimiento, por cuánto y con qué documentos. Sirve
    para preparar la oferta antes de que aparezca el llamado siguiente, que es
    justo lo que el Paso 3 necesita.
    """
    if df.empty or not rubros:
        return

    historial = df[mascara_rubros(df["cubso_descripcion"], rubros)].copy()
    historial = historial[~historial["vigencia"].isin(["VIGENTE", "POR CERRAR"])]
    if historial.empty:
        st.info(
            "El snapshot no tiene llamados anteriores para el rubro elegido."
        )
        return

    orden = (
        "fecha_inicio_ofertas"
        if "fecha_inicio_ofertas" in historial.columns
        else "fecha_publicacion"
    )
    historial[orden] = pd.to_datetime(historial[orden], errors="coerce", utc=True)
    historial = historial.sort_values(orden, ascending=False)

    st.markdown("#### Llamados anteriores de tu rubro")
    st.caption(
        f"{len(historial):,} procedimientos ya cerrados en "
        f"{', '.join(rubros).lower()}. Abre cualquiera para ver qué pidió la "
        "entidad: es la mejor referencia de lo que te van a exigir la próxima vez."
    )

    for _, h in historial.head(25).iterrows():
        fecha = h.get(orden)
        fecha_txt = pd.to_datetime(fecha).strftime("%d/%m/%Y") if pd.notna(fecha) else "sin fecha"
        monto_txt, _ = monto_declarado(h)
        titulo = texto_seguro(h.get("titulo"))
        with st.expander(
            f"{fecha_txt} · {titulo} · {monto_txt}",
            expanded=False,
        ):
            izq, der = st.columns([2, 1])
            with izq:
                st.markdown(f"**Qué pidieron**")
                st.write(
                    texto_seguro(h.get("descripcion"))
                    or "El release no trae descripción del objeto."
                )
                st.caption(f"Categoría {sigla('CUBSO')}: {texto_seguro(h.get('cubso_descripcion'))}")
            with der:
                st.markdown(f"**Entidad**")
                st.write(texto_seguro(h.get("entidad")))
                st.markdown(f"**Procedimiento**")
                st.write(texto_seguro(h.get("metodo_contratacion")))
                st.markdown(f"**Monto referencial**")
                st.write(monto_txt)

            docs_h = (
                documentos[documentos["ocid"].astype(str) == str(h.get("ocid"))]
                if documentos is not None and not documentos.empty
                else pd.DataFrame()
            )
            if not docs_h.empty:
                st.markdown("**Documentos publicados**")
                for _, d in docs_h.head(8).iterrows():
                    url = str(d.get("url") or "")
                    nombre = texto_seguro(d.get("titulo")) or texto_seguro(d.get("tipo_documento"))
                    if url.startswith("http"):
                        st.markdown(f"- [{nombre}]({url})")
                    else:
                        st.markdown(f"- {nombre}")
            else:
                st.caption("Este llamado no trajo documentos en la descarga.")


def ancla_llamado(ocid) -> str:
    """Id HTML estable para enlazar una tarjeta destacada con su llamado."""
    return "ll-" + re.sub(r"[^A-Za-z0-9_-]", "-", str(ocid))


def conteo_por_rubro(df: pd.DataFrame) -> pd.DataFrame:
    """Cuenta llamados por rubro de negocio.

    Un llamado puede caer en más de un rubro (una canasta de víveres toca
    alimentos y abarrotes), así que la suma de la columna puede superar el
    total de llamados. Se recorre el diccionario de rubros, no las filas: cada
    rubro resuelve su pertenencia con una sola comparación vectorizada.
    """
    if df.empty or "cubso_descripcion" not in df.columns:
        return pd.DataFrame(columns=["rubro", "llamados"])
    filas = []
    for rubro in RUBROS_NEGOCIO:
        n = int(mascara_rubros(df["cubso_descripcion"], [rubro]).sum())
        if n:
            filas.append({"rubro": rubro, "llamados": n})
    if not filas:
        return pd.DataFrame(columns=["rubro", "llamados"])
    return (
        pd.DataFrame(filas)
        .sort_values("llamados", ascending=False)
        .reset_index(drop=True)
    )


def selector_rubro(df: pd.DataFrame) -> str | None:
    """Dibuja el gráfico de rubros y devuelve el rubro elegido, si hay uno.

    El clic sobre una barra filtra la lista de llamados. Si la versión de
    Streamlit no admite selección en gráficos, se cae a un control equivalente
    para que la función siga estando disponible.
    """
    conteo = conteo_por_rubro(df)
    if conteo.empty:
        return None

    st.markdown("#### ¿Qué rubro quiero mirar?")
    st.caption(
        "Toca una barra para dejar solo los llamados de ese rubro. "
        "Un llamado puede pertenecer a más de un rubro."
    )

    seleccion = alt.selection_point(fields=["rubro"], name="pick", toggle=False)
    grafico = (
        alt.Chart(conteo)
        .mark_bar(cornerRadiusEnd=4, height=20)
        .encode(
            x=alt.X("llamados:Q", title=None),
            y=alt.Y("rubro:N", sort="-x", title=None,
                    axis=alt.Axis(labelLimit=280, labelFontSize=11)),
            color=alt.condition(seleccion, alt.value(NARANJA), alt.value(AZUL)),
            tooltip=[
                alt.Tooltip("rubro:N", title="Rubro"),
                alt.Tooltip("llamados:Q", title="Llamados"),
            ],
        )
        .add_params(seleccion)
        .properties(height=max(150, 28 * len(conteo)))
    )

    elegido = st.session_state.get("rubro_p2")
    try:
        evento = st.altair_chart(
            grafico, use_container_width=True, on_select="rerun", key="sel_rubro_p2"
        )
        puntos = (evento.get("selection") or {}).get("pick") or []
        if puntos:
            elegido = puntos[0].get("rubro")
            st.session_state["rubro_p2"] = elegido
    except TypeError:
        # Streamlit anterior a la selección en gráficos: control equivalente.
        st.altair_chart(grafico, use_container_width=True)
        opcion = st.selectbox(
            "Rubro",
            ["Todos los rubros"] + conteo["rubro"].tolist(),
            key="rubro_p2_fallback",
        )
        elegido = None if opcion == "Todos los rubros" else opcion
        st.session_state["rubro_p2"] = elegido

    if elegido:
        izq, der = st.columns([3, 1])
        with izq:
            st.success(f"Filtrando por rubro: **{elegido}**")
        with der:
            if st.button("Quitar filtro de rubro", key="limpiar_rubro_p2",
                         use_container_width=True):
                st.session_state["rubro_p2"] = None
                # El gráfico guarda su propia selección bajo su key: si no se
                # borra, el próximo rerun la devuelve en el evento y el filtro
                # se vuelve a aplicar solo. Borrar la key reinicia el widget.
                st.session_state.pop("sel_rubro_p2", None)
                st.rerun()
    return elegido


def render_llamados_destacados(df: pd.DataFrame) -> None:
    if df.empty:
        return
    cards = []
    for _, f in df.sort_values("dias_para_cierre").head(3).iterrows():
        dias = numero_seguro(f.get("dias_para_cierre"), default=np.nan)
        dias_txt, dias_lbl, _vencido = plazo_declarado(dias, f.get("origen_limite"))
        monto_txt, _monto_nota = monto_declarado(f)
        urgente = pd.notna(dias) and 0 <= dias <= 7
        badge = '<span class="ro-urgent-badge">🔥 Urgente</span>' if urgente else ''
        cards.append(
            # La tarjeta enlaza al mismo llamado en la lista de abajo, que se
            # marca con este id al renderizarse.
            f'<a class="ro-call-link" href="#{ancla_llamado(f.get("ocid"))}">'
            f'<div class="ro-call {"urgent" if urgente else ""}">'
            f'{badge}'
            f'<div class="ro-call-title">{texto_seguro(f.get("titulo"))}</div>'
            f'<div class="ro-call-value">{escape(monto_txt)}</div>'
            f'<div class="ro-call-note">⏰ {escape(dias_txt)} · {escape(dias_lbl.capitalize())}<br>'
            f'🏛️ {texto_seguro(f.get("entidad"))}<br>'
            f'📋 {texto_seguro(f.get("metodo_contratacion"))}</div>'
            '<div class="ro-call-cta">Ver este llamado abajo ↓</div>'
            '</div></a>'
        )
    st.markdown(
        '<div class="ro-calls">' + ''.join(cards) + '</div>',
        unsafe_allow_html=True,
    )


def render_formalidades_cards() -> None:
    st.markdown(
        f"""
        <div class="ro-formal-grid">
          <div class="ro-formal">
            <div class="ro-formal-title"><b>1</b> · 📝 Registro del proveedor</div>
            <div class="ro-formal-copy">Verifica que tu {sigla("RNP")} esté vigente para el tipo de compra.</div>
          </div>
          <div class="ro-formal">
            <div class="ro-formal-title"><b>2</b> · 📅 Fechas clave</div>
            <div class="ro-formal-copy">Registro, consultas, presentación de oferta y resultado.</div>
          </div>
          <div class="ro-formal">
            <div class="ro-formal-title"><b>3</b> · 📎 Papeles a presentar</div>
            <div class="ro-formal-copy">Bases, anexos y documentos que pide la entidad.</div>
          </div>
          <div class="ro-formal">
            <div class="ro-formal-title"><b>4</b> · ✋ Declaraciones y garantías</div>
            <div class="ro-formal-copy">Formatos y compromisos exigidos para postular correctamente.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


PALABRAS_VACIAS = {
    "servicio", "servicios", "para", "otros", "otras", "tipo", "tipos",
    "general", "generales", "segun", "contratacion", "adquisicion",
    "elaboracion", "distintos", "demas", "clase", "material", "materiales",
    "producto", "productos", "bien", "bienes", "sistema", "equipo", "equipos",
}


def _tokens_categoria(texto) -> frozenset:
    """Palabras significativas de una descripción CUBSO, para comparar afinidad."""
    palabras = re.findall(r"[a-z0-9]+", normalizar_busqueda(texto))
    return frozenset(
        p for p in palabras if len(p) > 3 and p not in PALABRAS_VACIAS
    )


@st.cache_data(show_spinner=False)
def _pool_documentos() -> pd.DataFrame:
    """Llamados que sí tienen documentos descargados, con sus tokens.

    Se calcula una sola vez por sesión porque recorre toda la tabla de
    convocatorias y el resultado no cambia mientras no se rehaga la descarga.
    """
    if convocatorias is None or convocatorias.empty or not OCIDS_CON_DOCUMENTOS:
        return pd.DataFrame()
    base = convocatorias[
        convocatorias["ocid"].astype(str).isin(OCIDS_CON_DOCUMENTOS)
    ].copy()
    if base.empty:
        return base
    clave = base["ocid"].astype(str)
    base["n_documentos"] = clave.map(DOCS_POR_OCID).fillna(0).astype(int)
    base["n_bases"] = clave.map(BASES_POR_OCID).fillna(0).astype(int)
    if "titulo" in base.columns:
        base = base[base["titulo"].notna()]
    if "cubso_descripcion" in base.columns:
        unicas = base["cubso_descripcion"].astype(str).unique()
        mapa_tokens = {u: _tokens_categoria(u) for u in unicas}
        base["tokens"] = base["cubso_descripcion"].astype(str).map(mapa_tokens)
    else:
        base["tokens"] = [frozenset()] * len(base)
    return base


def candidatos_similares(categoria=None, tipo_objeto=None, n: int = 25) -> pd.DataFrame:
    """Llamados con documentación, ordenados por parecido con la categoría elegida.

    Tres niveles de cercanía, en este orden:
      1. Misma categoría CUBSO.
      2. Categoría que comparte palabras significativas con la elegida.
      3. Mismo objeto de contratación (bien, servicio, obra).
    Si no hay contexto, devuelve los llamados con más documentación.
    """
    pool = _pool_documentos()
    if pool.empty:
        return pool

    partes = []
    if categoria and "cubso_descripcion" in pool.columns:
        misma = pool["cubso_descripcion"].astype(str) == str(categoria)
        exactos = pool[misma].copy()
        if not exactos.empty:
            exactos["afinidad"] = 999
            exactos["parecido"] = "Misma categoría"
            partes.append(exactos)

        objetivo = _tokens_categoria(categoria)
        if objetivo:
            resto = pool[~misma].copy()
            resto["afinidad"] = resto["tokens"].map(lambda t: len(t & objetivo))
            resto = resto[resto["afinidad"] > 0]
            if not resto.empty:
                resto["parecido"] = resto["tokens"].map(
                    lambda t: "Comparte: " + ", ".join(sorted(t & objetivo)[:3])
                )
                partes.append(resto)

    if tipo_objeto and "tipo_objeto" in pool.columns:
        mismo_objeto = pool[
            pool["tipo_objeto"].astype(str) == str(tipo_objeto)
        ].copy()
        if not mismo_objeto.empty:
            mismo_objeto["afinidad"] = 0
            mismo_objeto["parecido"] = f"Mismo objeto: {tipo_objeto}"
            partes.append(mismo_objeto)

    if not partes:
        general = pool.copy()
        general["afinidad"] = -1
        general["parecido"] = "Con más documentación"
        partes.append(general)

    salida = pd.concat(partes, ignore_index=True).drop_duplicates("ocid")
    return salida.sort_values(
        ["afinidad", "n_bases", "n_documentos"], ascending=False
    ).head(n)


def ir_a(pantalla: str, **estado) -> None:
    """Callback de navegación.

    Se ejecuta antes del rerun automático de Streamlit, evitando modificar
    el estado de widgets después de haber sido instanciados en la misma corrida.
    """
    for clave, valor in estado.items():
        st.session_state[clave] = valor
    st.session_state["pantalla"] = pantalla


# ---------------------------------------------------------------------------
# Detalle nominal de proveedores (popup de las tarjetas Q2 y Q5)
# ---------------------------------------------------------------------------
# Las tarjetas Q2 y Q5 muestran un conteo. Este bloque abre ese conteo y lo
# convierte en una lista con nombre, RUC y estado actual en el RNP, usando el
# mismo cruce que construir_maestro_periodo(): RUC de 11 dígitos extraído del
# proveedor_id del OCDS contra el padrón vigente.
COLUMNAS_NOMBRE_OCDS = (
    "proveedor_nombre", "nombre_proveedor", "proveedor", "adjudicatario",
    "nombre_adjudicatario", "razon_social", "supplier_name", "supplier",
)
COLUMNAS_NOMBRE_PADRON = (
    "razon_social", "nombre_o_razon_social", "razon_social_proveedor",
    "nombre_proveedor", "proveedor_nombre", "denominacion", "nombre",
    "proveedor",
)


def _columna_disponible(df: pd.DataFrame | None, candidatas) -> str | None:
    """Primera columna del DataFrame que coincide con la lista de candidatas.

    La comparación ignora mayúsculas y tildes para no depender del nombre
    exacto con el que se grabó el Parquet.
    """
    if df is None or df.empty:
        return None
    reales = {normalizar_busqueda(c): c for c in df.columns}
    for candidata in candidatas:
        real = reales.get(normalizar_busqueda(candidata))
        if real is not None:
            return real
    return None


def _a_bool(serie: pd.Series) -> pd.Series:
    """Convierte a booleano las banderas del padrón sin asumir un solo formato."""
    if pd.api.types.is_bool_dtype(serie):
        return serie.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce").fillna(0) > 0
    verdaderos = {
        "TRUE", "T", "1", "1.0", "SI", "SÍ", "S", "Y", "YES",
        "HABILITADO", "VIGENTE", "ACTIVO", "APTO",
    }
    return (
        serie.astype("string").str.strip().str.upper().isin(verdaderos).fillna(False)
    )


def detalle_proveedores_categoria(categoria) -> pd.DataFrame:
    """Proveedores que ganaron en la categoría durante el periodo elegido.

    Devuelve una fila por proveedor con su estado actual en el RNP. La suma de
    filas con habilitado=True coincide con competencia_vigente del maestro.
    """
    if not categoria or ocds_periodo is None or ocds_periodo.empty:
        return pd.DataFrame()
    if not {"cubso_descripcion", "proveedor_id"}.issubset(ocds_periodo.columns):
        return pd.DataFrame()

    base = ocds_periodo[
        ocds_periodo["cubso_descripcion"].astype(str) == str(categoria)
    ].dropna(subset=["proveedor_id"]).copy()
    if base.empty:
        return pd.DataFrame()

    base["ruc"] = (
        base["proveedor_id"].astype("string").str.extract(r"(\d{11})", expand=False)
    )
    base["clave"] = base["ruc"].fillna(base["proveedor_id"].astype("string"))

    col_nombre = _columna_disponible(base, COLUMNAS_NOMBRE_OCDS)
    base["nombre_ocds"] = (
        base[col_nombre].astype("string")
        if col_nombre
        else pd.Series(pd.NA, index=base.index, dtype="string")
    )
    base["monto_adjudicado"] = pd.to_numeric(
        base.get("monto_adjudicado"), errors="coerce"
    )
    base["fecha"] = pd.to_datetime(base.get("fecha"), errors="coerce", utc=True)

    detalle = (
        base.groupby("clave", as_index=False, observed=True)
        .agg(
            ruc=("ruc", "first"),
            nombre_ocds=("nombre_ocds", "first"),
            procesos=("ocid", "nunique"),
            monto=("monto_adjudicado", "sum"),
            ultima=("fecha", "max"),
        )
    )

    # Cruce con el padrón vigente del RNP.
    if padron is not None and not padron.empty:
        pad = padron.copy()
        if "ruc" not in pad.columns and "proveedor_id" in pad.columns:
            pad["ruc"] = pad["proveedor_id"].astype("string")
        if "ruc" in pad.columns:
            pad["ruc"] = pad["ruc"].astype("string")
            pad = pad.drop_duplicates(subset=["ruc"], keep="last")
            col_padron = _columna_disponible(pad, COLUMNAS_NOMBRE_PADRON)
            columnas = ["ruc"] + [
                c for c in ("es_habilitado", "es_apto_contratar") if c in pad.columns
            ]
            if col_padron and col_padron not in columnas:
                columnas.append(col_padron)
            recorte = pad[columnas].copy()
            if col_padron:
                recorte = recorte.rename(columns={col_padron: "nombre_padron"})
            detalle["ruc"] = detalle["ruc"].astype("string")
            detalle = detalle.merge(recorte, on="ruc", how="left")

    for columna in ("nombre_padron", "es_habilitado", "es_apto_contratar"):
        if columna not in detalle.columns:
            detalle[columna] = pd.NA

    detalle["habilitado"] = _a_bool(detalle["es_habilitado"])
    detalle["apto"] = _a_bool(detalle["es_apto_contratar"])
    detalle["estado"] = np.where(
        detalle["habilitado"], "Habilitado hoy", "Ya no figura habilitado"
    )
    detalle["proveedor"] = (
        detalle["nombre_padron"].astype("string")
        .fillna(detalle["nombre_ocds"].astype("string"))
        .fillna("RUC " + detalle["clave"].astype("string"))
    )
    detalle["ruc"] = detalle["ruc"].fillna("Sin RUC de 11 dígitos")

    return detalle.sort_values(
        ["habilitado", "monto"], ascending=[False, False]
    ).reset_index(drop=True)


def _panel_proveedores(categoria) -> None:
    """Contenido del popup: métricas, tarjetas y tabla descargable."""
    detalle = detalle_proveedores_categoria(categoria)

    st.markdown(
        f'<div class="ro-focus-name" style="font-size:17px">{texto_seguro(categoria)}</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"Ganadores del periodo {periodo_txt}, cruzados contra el padrón vigente "
        f"del RNP por RUC."
    )

    if detalle.empty:
        st.info(
            "No hay adjudicaciones con proveedor identificado en esta categoría "
            "para el periodo seleccionado."
        )
        return

    total = len(detalle)
    habilitados = int(detalle["habilitado"].sum())
    m1, m2, m3 = st.columns(3)
    m1.metric("Ganaron en el periodo", f"{total}")
    m2.metric("Siguen habilitados", f"{habilitados}")
    m3.metric("Ya no figuran", f"{total - habilitados}")

    clave_widget = normalizar_busqueda(categoria)[:40].replace(" ", "_")
    f1, f2 = st.columns([1.1, 1.4])
    with f1:
        modo = st.radio(
            "Qué proveedores muestro",
            ["Solo habilitados hoy", "Todos los ganadores"],
            horizontal=False,
            key=f"prov_modo_{clave_widget}",
        )
    with f2:
        texto_busqueda = st.text_input(
            "Buscar por nombre o RUC",
            key=f"prov_busca_{clave_widget}",
            placeholder="parte del nombre o los primeros dígitos del RUC",
        )

    vista = detalle.copy()
    if modo == "Solo habilitados hoy":
        vista = vista[vista["habilitado"]]
    if texto_busqueda:
        objetivo = normalizar_busqueda(texto_busqueda)
        vista = vista[
            vista["proveedor"].astype(str).map(normalizar_busqueda).str.contains(objetivo, na=False)
            | vista["ruc"].astype(str).str.contains(objetivo, na=False)
        ]

    if vista.empty:
        st.info("Ningún proveedor coincide con ese filtro.")
        return

    if detalle["proveedor"].astype(str).str.startswith("RUC ").all():
        st.warning(
            "El Parquet cargado no trae la razón social del proveedor, así que se "
            "muestra el RUC. Para ver nombres, incluye la razón social en el padrón "
            "o en la ingesta OCDS."
        )

    # Tarjetas para las primeras filas: es la lectura rápida del popup.
    tarjetas = []
    for _, p in vista.head(12).iterrows():
        habil = bool(p["habilitado"])
        ultima = p.get("ultima")
        ultima_txt = (
            pd.to_datetime(ultima).strftime("%d/%m/%Y") if pd.notna(ultima) else "—"
        )
        tarjetas.append(
            f'<div class="ro-prov {"" if habil else "baja"}">'
            f'<div class="ro-prov-nombre">{texto_seguro(p["proveedor"])}</div>'
            f'<div class="ro-prov-meta">RUC {texto_seguro(p["ruc"])} · '
            f'{int(numero_seguro(p["procesos"]))} proceso(s) · '
            f'{escape(formato_soles(p["monto"]))} · última {escape(ultima_txt)}</div>'
            f'<span class="ro-prov-estado {"si" if habil else "no"}">'
            f'{"Habilitado hoy" if habil else "Ya no figura"}</span>'
            '</div>'
        )
    st.markdown(
        '<div class="ro-prov-grid">' + "".join(tarjetas) + '</div>',
        unsafe_allow_html=True,
    )
    if len(vista) > 12:
        st.caption(f"Se muestran 12 de {len(vista)} proveedores. La tabla trae el resto.")

    tabla_prov = vista[
        ["proveedor", "ruc", "estado", "procesos", "monto", "ultima"]
    ].rename(columns={
        "proveedor": "Proveedor",
        "ruc": "RUC",
        "estado": "Estado en el RNP",
        "procesos": "Procesos ganados",
        "monto": "Monto adjudicado",
        "ultima": "Última adjudicación",
    })
    st.dataframe(
        tabla_prov,
        width="stretch",
        hide_index=True,
        column_config={
            "Monto adjudicado": st.column_config.NumberColumn(format="S/ %.0f"),
            "Última adjudicación": st.column_config.DatetimeColumn(format="DD/MM/YYYY"),
        },
    )
    st.download_button(
        "Descargar la lista en CSV",
        tabla_prov.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"proveedores_{clave_widget or 'categoria'}.csv",
        mime="text/csv",
        key=f"prov_csv_{clave_widget}",
    )
    st.caption(
        "El estado proviene del padrón RNP descargado en la última corrida. "
        "Antes de decidir, confirma la vigencia del proveedor en el buscador del RNP."
    )


# st.dialog existe desde versiones recientes de Streamlit. Si no está
# disponible, el detalle se despliega en un expander para no romper la app.
_DECORADOR_DIALOGO = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)

if _DECORADOR_DIALOGO is not None:
    try:
        _dialogo = _DECORADOR_DIALOGO(
            "Proveedores de la categoría", width="large"
        )
    except TypeError:
        _dialogo = _DECORADOR_DIALOGO("Proveedores de la categoría")

    @_dialogo
    def abrir_popup_proveedores(categoria) -> None:
        _panel_proveedores(categoria)

else:
    def abrir_popup_proveedores(categoria) -> None:
        with st.expander("Proveedores de la categoría", expanded=True):
            _panel_proveedores(categoria)

# ---------------------------------------------------------------------------
# Encabezado, periodo global y preguntas de negocio
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="ro-hero">
      <div class="ro-hero-left">
        <span class="ro-kicker">📡 Data app · presentación final</span>
        <div class="ro-hero-title">Radar de Oportunidades en <span>Compras Públicas</span></div>
        <div class="ro-hero-sub">Encuentra categorías con compras reales, poca competencia conocida y contratos que tu negocio puede evaluar. Del millón de procesos del Estado, el llamado que tu empresa sí puede atender.</div>
      </div>
      <div class="ro-hero-meta">
        <div class="ro-chip">📊 {sigla("UIT")} {config.UIT_ANIO} · {MONEDA} {config.UIT_SOLES:,}</div>
        <div class="ro-chip">🏷️ {len(maestro):,} categorías {sigla("CUBSO")}</div>
        <div class="ro-chip">🔗 {sigla("OCDS")} × {sigla("RNP")} × {sigla("OECE")}</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

render_preguntas_negocio()

# Periodo histórico global: afecta demanda, competencia histórica, ticket,
# estacionalidad, ranking e índice en todo el recorrido.
if ocds is not None and not ocds.empty:
    fechas_hist = pd.to_datetime(ocds["fecha"], errors="coerce", utc=True)
    if "anio" in ocds.columns:
        anios_disponibles = sorted(
            pd.to_numeric(ocds["anio"], errors="coerce").dropna().astype(int).unique().tolist()
        )
    else:
        anios_disponibles = sorted(fechas_hist.dt.year.dropna().astype(int).unique().tolist())
else:
    anios_disponibles = list(getattr(config, "OCDS_ANIOS", []))

meses_disponibles = list(range(1, 13))

st.sidebar.markdown("### 🗓️ Periodo de análisis")
st.sidebar.caption("Estos filtros acompañan todo el dashboard.")
anios_seleccionados = st.sidebar.multiselect(
    "Años",
    anios_disponibles,
    default=anios_disponibles,
    help="Elige uno o varios años del histórico que quieres comparar.",
)
meses_seleccionados = st.sidebar.multiselect(
    "Meses",
    meses_disponibles,
    default=meses_disponibles,
    format_func=mes_nombre,
    help="Si eliges varios años, el mes se aplica a cada año seleccionado.",
)
st.markdown(
    f"""
    <div class="ro-period">
      <div class="ro-period-title">Periodo activo</div>
      <div class="ro-period-copy">{escape(resumen_periodo(anios_seleccionados, meses_seleccionados))}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not anios_seleccionados or not meses_seleccionados:
    st.sidebar.warning("Selecciona al menos un año y un mes.")
    st.info("Selecciona al menos un año y un mes para continuar.")
    st.stop()

ocds_periodo = filtrar_historico_periodo(
    ocds, anios_seleccionados, meses_seleccionados
)
maestro_periodo = construir_maestro_periodo(
    ocds_periodo, padron, convocatorias
)
periodo_txt = resumen_periodo(anios_seleccionados, meses_seleccionados)

PANTALLAS = [
    "1 · ¿Dónde me conviene buscar?",
    "2 · ¿Qué puedo postular hoy?",
    "3 · ¿Qué tengo que preparar?",
    "Fuentes y actualización",
]
if st.session_state.get("pantalla") not in PANTALLAS:
    st.session_state["pantalla"] = PANTALLAS[0]

pantalla = st.radio(
    "Recorrido",
    PANTALLAS,
    key="pantalla",
    horizontal=True,
    label_visibility="collapsed",
)

if st.session_state.categoria and not pantalla.startswith("1"):
    st.caption(
        f"Categoría elegida: **{st.session_state.categoria}** · "
        f"Histórico analizado: **{periodo_txt}**"
    )


# ===========================================================================
# PANTALLA 1 — DÓNDE ME CONVIENE BUSCAR
# ===========================================================================
if pantalla.startswith("1"):
    titulo_paso(
        "PASO 1 · ENCONTRAR OPORTUNIDADES",
        "Primero encuentra categorías que valga la pena revisar",
        f"Analizamos {periodo_txt}. Combinamos cuánto compró el Estado, cuántos ganadores siguen habilitados y si el tamaño promedio del contrato está al alcance de una micro o pequeña empresa.",
    )

    st.markdown(
        '<div class="ro-filter-title">Ajusta la búsqueda a lo que tu negocio puede atender</div>',
        unsafe_allow_html=True,
    )
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        rubros_elegidos = st.multiselect(
            "Rubro al que pertenezco",
            list(RUBROS_NEGOCIO.keys()),
            # Con key, Streamlit conserva la selección entre pantallas: el
            # rubro elegido aquí es el que usa el Paso 2.
            key="rubros_paso1",
            help=(
                "Atajo por giro comercial: agrupa varias palabras a la vez. "
                "El rubro que marques aquí acompaña al Paso 2."
            ),
        )
    with f2:
        busqueda = st.text_input(
            "¿Qué vendes o qué servicio das?",
            placeholder="alimentación, catering, víveres...",
            help=(
                "Busca dentro de la descripción CUBSO. Ignora mayúsculas y tildes. "
                "Puedes escribir varias palabras separadas por coma y trae las "
                "categorías que contengan cualquiera de ellas."
            ),
        )
    with f3:
        bandas_comp = ["Todas"] + [
            b
            for b in (config.BANDAS_COMPETENCIA_ETIQUETAS + ["Competencia no determinada"])
            if b in set(maestro_periodo["banda_competencia"].dropna().astype(str))
        ] if not maestro_periodo.empty else ["Todas"]
        banda_elegida = st.selectbox(
            "Q2 · Competencia conocida",
            bandas_comp,
            format_func=lambda x: "Todas" if x == "Todas" else etiqueta_competencia(x),
            help="Cuenta ganadores del periodo elegido que siguen habilitados hoy en el RNP.",
        )
    with f4:
        bandas_disponibles = [
            b
            for b in config.BANDAS_TICKET_ETIQUETAS
            if not maestro_periodo.empty
            and b in set(maestro_periodo["banda_ticket"].dropna().astype(str))
        ]
        bandas_elegidas = st.multiselect(
            "Q4 · Tamaño promedio del contrato",
            bandas_disponibles,
            default=bandas_disponibles,
            help="Las bandas se expresan en UIT para que puedas comparar el tamaño de los contratos con mayor facilidad.",
        )

    # Segunda fila del panel: el índice mínimo y los dos interruptores de
    # alcance, separados de los selectores para que las cajas de arriba
    # queden alineadas entre sí.
    g1, g2, g3 = st.columns([1, 1.5, 1.5])
    with g1:
        indice_min = st.slider(
            "Índice mínimo",
            0, 100, 0, step=5,
            help="Úsalo para quedarte solo con las categorías mejor posicionadas dentro del periodo seleccionado.",
        )
    with g2:
        st.markdown("<div style='height:30px'></div>", unsafe_allow_html=True)
        solo_aptas = st.checkbox(
            "Solo categorías con compras repetidas",
            value=True,
            help=(
                f"Deja fuera compras aisladas: exige al menos {config.MINIMO_PROCESOS_MERCADO} "
                f"procesos y {config.MINIMO_DEMANDA_UIT_MERCADO} UIT acumuladas en el periodo."
            ),
        )
    with g3:
        st.markdown("<div style='height:30px'></div>", unsafe_allow_html=True)
        solo_accionables = st.checkbox(
            "Solo categorías convocadas el último día registrado",
            value=False,
            help=(
                f"Muestra las categorías que tuvieron convocatorias con inicio de ofertas "
                f"el {ultima_fecha_snapshot_txt}, la fecha más reciente del snapshot. "
                f"Indica actividad reciente en la fuente, no vigencia para postular hoy."
            ),
        )

    filtrado = maestro_periodo.copy()

    if solo_aptas and not filtrado.empty:
        filtrado = filtrado[
            filtrado["apto_para_ranking"].astype("object").fillna(False).astype(bool)
        ]
    if rubros_elegidos and not filtrado.empty:
        filtrado = filtrado[mascara_rubros(filtrado["cubso_descripcion"], rubros_elegidos)]
    if busqueda and not filtrado.empty:
        terminos = [
            normalizar_busqueda(t)
            for t in re.split(r"[,;]", busqueda)
            if normalizar_busqueda(t)
        ]
        if terminos:
            patron = "|".join(re.escape(t) for t in terminos)
            descripcion_normalizada = (
                filtrado["cubso_descripcion"].astype(str).map(normalizar_busqueda)
            )
            filtrado = filtrado[
                descripcion_normalizada.str.contains(patron, na=False, regex=True)
            ]
    if solo_accionables and not filtrado.empty:
        filtrado = filtrado[
            filtrado["cubso_descripcion"].astype(str).isin(categorias_ultima_publicacion)
        ]
    if banda_elegida != "Todas" and not filtrado.empty:
        filtrado = filtrado[
            filtrado["banda_competencia"].astype(str) == banda_elegida
        ]
    if bandas_elegidas and not filtrado.empty:
        filtrado = filtrado[
            filtrado["banda_ticket"].astype(str).isin(bandas_elegidas)
        ]
    if indice_min > 0 and not filtrado.empty:
        filtrado = filtrado[filtrado["indice_oportunidad"] >= indice_min]

    desierto = (
        filtrado["mercado_desierto"].astype("object").fillna(False).astype(bool)
        if not filtrado.empty else pd.Series(dtype=bool)
    )
    indice_max = (
        numero_seguro(filtrado["indice_oportunidad"].max())
        if len(filtrado) else 0
    )

    render_kpis([
        {
            "label": "Categorías para revisar",
            "value": f"{len(filtrado):,}",
            "note": "Categorías que cumplen los filtros actuales",
            "accent": "blue",
        },
        {
            "label": "Q1 · Compras adjudicadas",
            "value": formato_soles(filtrado["demanda_soles"].sum()) if len(filtrado) else formato_soles(0),
            "note": f"Total del periodo: {periodo_txt}",
            "accent": "orange",
        },
        {
            "label": "Convocatorias del último día registrado",
            "value": f"{int(ultimos_procedimientos_snapshot):,}",
            "note": f"Inicio de ofertas el {ultima_fecha_snapshot_txt} · validar vigencia en SEACE",
            "accent": "purple",
        },
        {
            "label": "Q2 · Sin ganador histórico habilitado",
            "value": f"{int(desierto.sum()):,}",
            "note": "Hubo ganadores en el periodo, pero ninguno sigue habilitado",
            "accent": "orange",
        },
        {
            "label": "Mejor índice",
            "value": f"{indice_max:.0f}",
            "note": "Mayor puntaje entre las categorías filtradas",
            "accent": "blue",
        },
    ])

    st.markdown(
        f"""
        <div class="ro-index-help">
          <h4>¿Qué es el índice de oportunidad?</h4>
          <p>Es una <strong>brújula de 0 a 100</strong> para ordenar categorías. No dice que tengas 66% o 80% de probabilidad de ganar.</p>
          <p><strong>1.</strong> Primero combinamos cuánto compró el Estado (<strong>55%</strong>) con qué tan despejada está la competencia conocida (<strong>45%</strong>).</p>
          <p><strong>2.</strong> Después ajustamos ese potencial según el tamaño promedio del contrato: cuanto más manejable para una {sigla("MYPE")}, menos castigo recibe.</p>
          <p><strong>3.</strong> Sirve para decidir <strong>qué revisar primero</strong>. El índice se recalcula con el periodo y los filtros elegidos.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if filtrado.empty:
        st.info(
            "No encontramos categorías con esa combinación de periodo y filtros. "
            "Prueba ampliar los meses, quitar algún filtro, cambiar de rubro o buscar otra palabra."
        )
        st.stop()

    top = filtrado.nlargest(200, "indice_oportunidad")
    opciones = top["cubso_descripcion"].tolist()
    if st.session_state.categoria not in opciones:
        st.session_state.categoria = opciones[0]

    foco = st.selectbox(
        "Categoría que quiero revisar",
        opciones,
        index=opciones.index(st.session_state.categoria),
        key="categoria",
        help="Elige una categoría para ver la respuesta completa a las cinco preguntas.",
    )
    fila = filtrado[filtrado["cubso_descripcion"] == foco].iloc[0]
    est_foco = fila

    st.markdown(
        f"""
        <div class="ro-focus-head">
          <div>
            <div style="font-size:10px;color:{APAGADO};font-weight:800;letter-spacing:.05em">CATEGORÍA ELEGIDA</div>
            <div class="ro-focus-name">{texto_seguro(foco)}</div>
            <div style="font-size:11px;color:{APAGADO};margin-top:4px">Periodo: {escape(periodo_txt)}</div>
          </div>
          <div class="ro-index">
            <small>ÍNDICE</small>
            <strong>{numero_seguro(fila.get('indice_oportunidad')):.0f}</strong>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_respuestas_categoria(fila, est_foco)

    # Valores de la categoría en foco usados en ambos paneles visuales.
    vigentes_cat = int(round(numero_seguro(fila.get("competencia_vigente"))))
    ganaron_cat = int(round(numero_seguro(fila.get("ganadores_historicos"))))
    ticket_cat = numero_seguro(fila.get("ticket_uit"))
    salieron = numero_seguro(fila.get("salieron_del_registro"))

    # Puente entre el conteo de las tarjetas Q2/Q5 y el detalle nominal.
    # El popup responde "¿quiénes son esos proveedores?" sin salir de la vista.
    abrir_proveedores = st.button(
        f"👥 Ver los {vigentes_cat} proveedores que siguen habilitados",
        key="ver_proveedores_top",
        use_container_width=True,
        help=(
            "Abre la lista con nombre, RUC, procesos ganados y estado actual "
            "en el RNP de los proveedores que ganaron en esta categoría."
        ),
    )

    # Dos paneles balanceados: mapa a la izquierda e índice a la derecha.
    # El gráfico del índice comienza a la misma altura que el mapa.
    izq, der = st.columns([1.35, 1.05], gap="large")

    with izq:
        st.markdown("#### Mapa de categorías")
        st.caption(
            "Cada burbuja es una categoría. Más a la derecha significa más compras adjudicadas. "
            "Más arriba significa menos ganadores históricos que siguen habilitados. "
            "Una burbuja más grande indica un contrato promedio más accesible."
        )
        mapa = top.head(120).copy()
        mapa["destacada"] = mapa["cubso_descripcion"] == foco
        mapa["competencia_ui"] = mapa["banda_competencia"].map(etiqueta_competencia)

        color_ui = {
            etiqueta_competencia(k): v for k, v in COLOR_BANDA.items()
        }

        base = alt.Chart(mapa).mark_circle(opacity=0.78).encode(
            x=alt.X(
                "demanda_soles:Q",
                scale=alt.Scale(type="log"),
                title="Q1 · Compras adjudicadas en el periodo (escala log)",
            ),
            y=alt.Y(
                "competencia_vigente:Q",
                scale=alt.Scale(type="symlog", reverse=True),
                title="Q2 · Ganadores del periodo que siguen habilitados",
            ),
            size=alt.Size(
                "accesibilidad:Q",
                title="Q4 · Accesibilidad del contrato",
                scale=alt.Scale(range=[70, 460]),
            ),
            color=alt.Color(
                "competencia_ui:N",
                title="Competencia conocida",
                scale=alt.Scale(
                    domain=list(color_ui.keys()),
                    range=list(color_ui.values()),
                ),
            ),
            tooltip=[
                alt.Tooltip("cubso_descripcion:N", title="Categoría"),
                alt.Tooltip("indice_oportunidad:Q", title="Índice", format=".0f"),
                alt.Tooltip("demanda_soles:Q", title="Compras adjudicadas", format=",.0f"),
                alt.Tooltip("ganadores_historicos:Q", title="Ganadores del periodo"),
                alt.Tooltip("competencia_vigente:Q", title="Siguen habilitados"),
                alt.Tooltip("ticket_uit:Q", title="Contrato promedio (UIT)", format=".1f"),
            ],
        )
        anillo = alt.Chart(mapa[mapa["destacada"]]).mark_point(
            size=650, color=NARANJA, strokeWidth=4, filled=False
        ).encode(
            x=alt.X("demanda_soles:Q", scale=alt.Scale(type="log")),
            y=alt.Y("competencia_vigente:Q", scale=alt.Scale(type="symlog", reverse=True)),
        )
        chart = (
            (base + anillo)
            .properties(height=440)
            .configure_view(strokeWidth=0, fill="transparent")
            .configure_axis(
                gridColor="#E8ECF1",
                gridWidth=1,
                labelColor=APAGADO,
                titleColor=TINTA,
                titleFontSize=13,
                titleFontWeight=700,
                labelFontSize=11,
            )
            .configure_legend(
                labelColor=APAGADO,
                titleColor=TINTA,
                titleFontSize=12,
                labelFontSize=11,
                orient="bottom",
                padding=15,
            )
            .configure_title(fontSize=16, fontWeight=800, color=TINTA)
        )
        st.altair_chart(chart, use_container_width=True)

    with der:
        espacio = numero_seguro(fila.get("espacio_mercado"))
        acces = numero_seguro(fila.get("accesibilidad"))
        potencial = numero_seguro(fila.get("potencial_mercado")) / 100
        demanda_esc = numero_seguro(fila.get("demanda_escalada"))

        # Gráfico ampliado y alineado con el mapa de categorías.
        st.markdown(
            f"#### Cómo se construyó este índice: {numero_seguro(fila.get('indice_oportunidad')):.0f}/100"
        )
        st.caption(
            "Los tres componentes están expresados en una escala de 0 a 1. Cuanto más larga la barra, mayor aporte al potencial de la categoría."
        )
        desglose = pd.DataFrame({
            "Componente": [
                "Nivel de compras",
                "Espacio frente a competencia",
                "Accesibilidad del contrato",
            ],
            "Valor": [demanda_esc, espacio, acces],
        })
        grafico_indice = (
            alt.Chart(desglose)
            .mark_bar(
                color=AZUL,
                cornerRadiusEnd=8,
                size=38,
            )
            .encode(
                x=alt.X(
                    "Valor:Q",
                    scale=alt.Scale(domain=[0, 1]),
                    title=None,
                    axis=alt.Axis(
                        format=".1f",
                        tickCount=6,
                        grid=True,
                        gridColor="#E9EDF1",
                        labelColor=APAGADO,
                        labelFontSize=11,
                    ),
                ),
                y=alt.Y(
                    "Componente:N",
                    sort=None,
                    title=None,
                    axis=alt.Axis(
                        labelLimit=220,
                        labelPadding=12,
                        labelColor=TINTA,
                        labelFontSize=12,
                        labelFontWeight=700,
                    ),
                ),
                tooltip=[
                    alt.Tooltip("Componente", title="Componente"),
                    alt.Tooltip("Valor:Q", format=".2f", title="Valor"),
                ],
            )
            .properties(height=280)
            .configure_view(strokeWidth=0, fill="transparent")
            .configure_axis(labelColor=APAGADO, titleColor=TINTA)
        )
        st.altair_chart(grafico_indice, use_container_width=True)
        st.caption(
            f"Potencial {potencial:.2f} × accesibilidad {acces:.2f} = "
            f"{numero_seguro(fila.get('indice_oportunidad')):.0f} puntos."
        )

        st.markdown(
            f"""
            <div class="ro-reading">
              <h4>Qué me dice esta categoría</h4>
              <p>En <strong>{escape(periodo_txt)}</strong>, el Estado adjudicó <strong>{escape(formato_soles(fila.get('demanda_soles')))}</strong> en esta categoría.</p>
              <p>En ese periodo ganaron {ganaron_cat} proveedores; <strong>{vigentes_cat} siguen habilitados hoy</strong> en el {sigla("RNP")}.</p>
              <p>El contrato promedio equivale a <strong>{ticket_cat:.1f} {sigla("UIT")}</strong>. El día más reciente del snapshot es el <strong>{ultima_fecha_snapshot_txt}</strong>, con <strong>{int(ultimos_procedimientos_snapshot):,} convocatorias</strong> cuyo plazo de ofertas abrió esa fecha. La vigencia para postular se confirma en el {sigla("SEACE")}.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Q5 y Q3 salen de las columnas anteriores y se dibujan en una sola fila:
    # así las seis tarjetas arrancan a la misma altura, sin depender del alto
    # que tomen el mapa, el gráfico del índice o el texto de lectura.
    q5_col, q3_col = st.columns([1.35, 1.05], gap="large")

    with q5_col:
        q("Q5", "¿Cuántos de los ganadores del periodo siguen habilitados hoy?")
        q5c1, q5c2, q5c3 = st.columns(3)
        q5c1.metric(
            "Ganaron en el periodo",
            f"{ganaron_cat}",
            help="Proveedores distintos que ganaron adjudicaciones en el periodo seleccionado.",
        )
        q5c2.metric(
            "Siguen habilitados hoy",
            f"{vigentes_cat}",
            help="Ganadores del periodo que actualmente figuran habilitados en el RNP.",
        )
        q5c3.metric(
            "Ya no figuran habilitados",
            f"{int(round(salieron))}",
            help="Ganadores del periodo que ya no aparecen habilitados en el cruce actual con el RNP.",
        )
        st.caption(
            "Lectura Q5: histórico del periodo seleccionado comparado con la situación actual en el RNP."
        )
        if st.button(
            "👥 Ver quiénes son",
            key="ver_proveedores_q5",
            use_container_width=True,
        ):
            abrir_proveedores = True

    with q3_col:
        q("Q3", "¿En qué mes se concentraron más compras dentro del periodo?")
        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Mes con más compras",
            mes_nombre(fila.get("mes_pico")),
            help="Mes del periodo seleccionado con el mayor monto adjudicado en esta categoría.",
        )
        c2.metric(
            "Peso de ese mes",
            f"{numero_seguro(fila.get('concentracion_mes')) * 100:.0f}%",
            help="Porcentaje del monto del periodo que cayó en el mes con mayor compra.",
        )
        c3.metric(
            "Meses con actividad",
            f"{int(round(numero_seguro(fila.get('meses_activos'))))}/{len(meses_seleccionados)}",
            help="Cantidad de meses seleccionados en los que hubo adjudicaciones para esta categoría.",
        )
        st.caption(
            "Lectura Q3: sirve para preparar compras y documentos antes del mes pico."
        )

    if abrir_proveedores:
        abrir_popup_proveedores(foco)

    st.button(
        "Revisar oportunidades actuales de esta categoría →",
        type="primary",
        use_container_width=True,
        on_click=ir_a,
        args=(PANTALLAS[1],),
    )

    st.markdown("#### Lista priorizada de categorías")
    st.caption(
        "Sirve como respaldo para comparar. El índice ordena qué revisar primero dentro del periodo y filtros actuales."
    )

    cols_rank = [
        c for c in [
            "cubso_descripcion", "indice_oportunidad", "demanda_soles",
            "n_procesos", "ganadores_historicos", "competencia_vigente",
            "salieron_del_registro", "banda_competencia", "ticket_promedio",
            "ticket_uit", "banda_ticket", "mes_pico",
        ] if c in filtrado.columns
    ]

    tabla = top[cols_rank].copy()
    if "banda_competencia" in tabla.columns:
        tabla["banda_competencia"] = tabla["banda_competencia"].map(etiqueta_competencia)

    tabla = tabla.rename(columns={
        "cubso_descripcion": "Categoría",
        "indice_oportunidad": "Índice",
        "demanda_soles": "Q1 · Compras del periodo",
        "n_procesos": "Procesos",
        "ganadores_historicos": "Q5 · Ganaron en el periodo",
        "competencia_vigente": "Q5 · Siguen habilitados",
        "salieron_del_registro": "Ya no figuran habilitados",
        "banda_competencia": "Q2 · Competencia conocida",
        "ticket_promedio": "Q4 · Contrato promedio",
        "ticket_uit": "Q4 · Contrato (UIT)",
        "banda_ticket": "Q4 · Tamaño",
        "mes_pico": "Q3 · Mes con más compras",
    })
    if "Q3 · Mes con más compras" in tabla.columns:
        tabla["Q3 · Mes con más compras"] = tabla["Q3 · Mes con más compras"].map(mes_nombre)

    st.dataframe(
        tabla,
        width="stretch",
        hide_index=True,
        column_config={
            "Índice": st.column_config.ProgressColumn(
                format="%.0f", min_value=0, max_value=100,
                help="Puntaje comparativo para ordenar categorías; no es una probabilidad de ganar.",
            ),
            "Q1 · Compras del periodo": st.column_config.NumberColumn(format="S/ %.0f"),
            "Q4 · Contrato promedio": st.column_config.NumberColumn(format="S/ %.0f"),
            "Q4 · Contrato (UIT)": st.column_config.NumberColumn(
                format="%.1f",
                help="UIT = Unidad Impositiva Tributaria.",
            ),
            "Q5 · Ganaron en el periodo": st.column_config.NumberColumn(format="%d"),
            "Q5 · Siguen habilitados": st.column_config.NumberColumn(
                format="%d",
                help="De los ganadores del periodo, cuántos siguen habilitados hoy en el RNP.",
            ),
        },
    )


# ===========================================================================
# PANTALLA 2 — QUÉ PUEDO POSTULAR HOY
# ===========================================================================
elif pantalla.startswith("2"):
    titulo_paso(
        "PASO 2 · OPORTUNIDADES ACTUALES",
        "Revisa lo último detectado y confirma qué sigue vigente en SEACE",
        "El histórico te ayuda a elegir una categoría. Aquí separamos la última cobertura disponible en datos abiertos de la vigencia oficial que debes confirmar en SEACE antes de postular.",
        dark=True,
    )

    st.markdown(
        f"""
        <div class="ro-period">
          <div class="ro-period-title">Contexto que llevas desde el Paso 1</div>
          <div class="ro-period-copy">Histórico analizado: <b>{escape(periodo_txt)}</b>. La tabla operativa usa la última cobertura {sigla("OCDS")} descargada del {sigla("OECE")}; la vigencia final se confirma en el {sigla("SEACE")}.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if convocatorias is None:
        st.warning(
            "Todavía no hay una corrida de llamados cargada. Ejecuta monitor_convocatorias.py para actualizar esta sección."
        )
        st.stop()

    vigentes = convocatorias[
        convocatorias["vigencia"].isin(["VIGENTE", "POR CERRAR"])
    ]

    if vigentes.empty:
        # El snapshot puede llegar con desfase respecto del SEACE. En ese caso
        # mostramos la cobertura real disponible y evitamos afirmar que no hay
        # oportunidades abiertas.
        fechas_publicacion = pd.to_datetime(
            convocatorias.get(COLUMNA_FECHA_CONVOCATORIA),
            errors="coerce",
            utc=True,
        )
        fechas_cierre = pd.to_datetime(
            convocatorias.get("fecha_cierre_ofertas"), errors="coerce", utc=True
        )
        fecha_fuente = fechas_publicacion.max() if fechas_publicacion.notna().any() else pd.NaT
        cierre_fuente = fechas_cierre.max() if fechas_cierre.notna().any() else pd.NaT
        ahora_utc = pd.Timestamp.now(tz="UTC")
        desfase_dias = (
            max(0, int((ahora_utc - fecha_fuente).total_seconds() // 86400))
            if pd.notna(fecha_fuente) else None
        )

        fecha_fuente_txt = (
            fecha_fuente.strftime("%d/%m/%Y") if pd.notna(fecha_fuente) else "No disponible"
        )
        cierre_fuente_txt = (
            cierre_fuente.strftime("%d/%m/%Y") if pd.notna(cierre_fuente) else "No disponible"
        )
        desfase_txt = (
            f"{desfase_dias} días" if desfase_dias is not None else "No calculable"
        )

        st.markdown(
            f'<div class="ro-aviso"><b>La descarga disponible no permite confirmar llamados abiertos hoy.</b><br>'
            f'La convocatoria más reciente de este snapshot llega al <b>{fecha_fuente_txt}</b> '
            f'y la mayor fecha de cierre encontrada es <b>{cierre_fuente_txt}</b>. '
            f'El desfase frente a hoy es de <b>{desfase_txt}</b>. Esto describe la cobertura '
            f'de los datos abiertos, no significa que el {sigla("SEACE")} no tenga oportunidades vigentes.</div>',
            unsafe_allow_html=True,
        )

        render_kpis([
            {
                "label": "Última convocatoria disponible",
                "value": fecha_fuente_txt,
                "note": "Fecha de convocatoria más reciente del snapshot",
                "accent": "orange",
            },
            {
                "label": "Mayor cierre disponible",
                "value": cierre_fuente_txt,
                "note": "Última fecha de cierre encontrada en el snapshot",
                "accent": "blue",
            },
            {
                "label": "Convocatorias del último día registrado",
                "value": f"{int(ultimos_procedimientos_snapshot):,}",
                "note": f"Con inicio de ofertas el {ultima_fecha_snapshot_txt}",
                "accent": "purple",
            },
        ])

        seace_col, contexto_col = st.columns([1.0, 1.45], gap="large")
        with seace_col:
            st.markdown("#### Confirmación oficial")
            st.markdown(
                f"Para saber qué puedes postular <b>hoy</b>, valida la categoría en el "
                f"buscador público del {sigla('SEACE')}. El {sigla('OECE')} lo presenta "
                f"como el buscador de procedimientos vigentes.",
                unsafe_allow_html=True,
            )
            st.link_button(
                "Abrir oportunidades vigentes en SEACE ↗",
                SEACE_BUSCADORES_URL,
                type="primary",
                use_container_width=True,
            )
            if st.session_state.categoria:
                st.info(
                    "Categoría para buscar en SEACE: "
                    f"{st.session_state.categoria}"
                )
            st.caption(
                "Antes de preparar una oferta, confirma cronograma, registro de participantes, "
                "bases y fecha de cierre directamente en SEACE."
            )

        with contexto_col:
            st.markdown("#### Convocatorias más recientes del snapshot")
            st.caption(
                "Sirven para ver qué venía convocándose en la categoría. No se presentan como "
                "oportunidades abiertas porque la fuente disponible tiene desfase."
            )

            recientes = convocatorias.copy()
            recientes["fecha_publicacion"] = pd.to_datetime(
                recientes.get(COLUMNA_FECHA_CONVOCATORIA), errors="coerce", utc=True
            )
            recientes["fecha_cierre_ofertas"] = pd.to_datetime(
                recientes.get("fecha_cierre_ofertas"), errors="coerce", utc=True
            )

            categoria_foco = st.session_state.categoria
            if categoria_foco and "cubso_descripcion" in recientes.columns:
                recientes_cat = recientes[
                    recientes["cubso_descripcion"] == categoria_foco
                ].copy()
                if not recientes_cat.empty:
                    recientes = recientes_cat
                    st.caption(f"Mostrando primero la categoría elegida: {categoria_foco}")
                else:
                    st.caption(
                        "El snapshot no tiene registros recientes para la categoría elegida; "
                        "se muestran los procedimientos más recientes de toda la descarga."
                    )

            recientes = recientes.sort_values("fecha_publicacion", ascending=False).head(20)
            columnas_recientes = [
                c for c in [
                    "fecha_publicacion", "entidad", "titulo", "metodo_contratacion",
                    "monto_referencial", "fecha_cierre_ofertas", "vigencia"
                ] if c in recientes.columns
            ]
            tabla_recientes = recientes[columnas_recientes].rename(columns={
                "fecha_publicacion": "Inicio de ofertas",
                "entidad": "Entidad",
                "titulo": "Procedimiento",
                "metodo_contratacion": "Tipo",
                "monto_referencial": "Monto referencial",
                "fecha_cierre_ofertas": "Cierre en snapshot",
                "vigencia": "Estado en snapshot",
            })
            st.dataframe(
                tabla_recientes,
                width="stretch",
                hide_index=True,
                column_config={
                    "Inicio de ofertas": st.column_config.DatetimeColumn(format="DD/MM/YYYY"),
                    "Cierre en snapshot": st.column_config.DatetimeColumn(format="DD/MM/YYYY"),
                    "Monto referencial": st.column_config.NumberColumn(format="S/ %.0f"),
                },
            )

        st.stop()

    st.caption(
        "La vigencia de esta lista se calcula con la última descarga disponible. "
        "Confirma siempre el cronograma y el estado oficial en SEACE antes de postular."
    )
    st.link_button(
        "Abrir buscador oficial de oportunidades en SEACE ↗",
        SEACE_BUSCADORES_URL,
        use_container_width=False,
    )

    c1, c2, c3 = st.columns([2, 1.3, 1.4])
    with c1:
        filtrar_categoria = st.checkbox(
            "Solo la categoría exacta que elegí (no todo el rubro)",
            value=bool(st.session_state.categoria),
            disabled=not st.session_state.categoria,
            help=(
                "La categoría es una descripción CUBSO literal, una entre 38 mil. "
                "El rubro agrupa muchas categorías del mismo giro: alimentación, "
                "catering, víveres, desayunos y demás caen en Alimentos. Con esta "
                "casilla marcada se exigen ambas condiciones a la vez, así que "
                "puede quedar vacío aunque el rubro sí tenga llamados."
            ),
        )
    with c2:
        solo_urgentes = st.checkbox(
            "Solo los que cierran en 7 días o menos",
            help="Útil para separar lo urgente de lo que todavía da tiempo para preparar.",
        )
    with c3:
        solo_con_docs = st.checkbox(
            "Solo llamados con documentos publicados",
            value=False,
            disabled=not OCIDS_CON_DOCUMENTOS,
            help=(
                "Deja únicamente los llamados cuyas bases y anexos sí vinieron en la "
                "descarga. Son los casos donde el Paso 3 muestra documentos reales."
            ),
        )

    rubro_elegido = selector_rubro(vigentes)

    mostrar = vigentes.copy()
    if rubro_elegido:
        mostrar = mostrar[mascara_rubros(mostrar["cubso_descripcion"], [rubro_elegido])]
    if filtrar_categoria and st.session_state.categoria:
        mostrar = mostrar[
            mostrar["cubso_descripcion"] == st.session_state.categoria
        ]
    if solo_urgentes:
        mostrar = mostrar[mostrar["vigencia"] == "POR CERRAR"]
    if solo_con_docs and OCIDS_CON_DOCUMENTOS:
        mostrar = mostrar[mostrar["ocid"].astype(str).isin(OCIDS_CON_DOCUMENTOS)]

    # Los montos en cero no son ceros: o estan reservados por ley o la entidad
    # no los publico. Sumarlos junto a los publicados da un total incompleto y
    # una mediana de cero. Se agregan solo los publicados y la nota declara
    # sobre cuantos llamados se calculo.
    _montos_publicados = pd.to_numeric(
        mostrar.get("monto_referencial"), errors="coerce"
    ).dropna()
    _montos_publicados = _montos_publicados[_montos_publicados > 0]
    _nota_montos = (
        f"Sobre {len(_montos_publicados):,} de {len(mostrar):,} llamados con monto publicado"
    )

    render_kpis([
        {
            "label": "Llamados abiertos",
            "value": f"{len(mostrar):,}",
            "note": "Oportunidades con plazo de oferta vigente",
            "accent": "orange",
        },
        {
            "label": "Monto referencial total",
            "value": formato_soles(_montos_publicados.sum()) if len(_montos_publicados) else "No publicado",
            "note": _nota_montos,
            "accent": "blue",
        },
        {
            "label": "Cierran esta semana",
            "value": f"{int((mostrar['vigencia'] == 'POR CERRAR').sum()):,}",
            "note": "Plazo de 7 días o menos",
            "accent": "orange",
        },
        {
            "label": "Entidades comprando",
            "value": f"{mostrar['entidad'].nunique():,}",
            "note": "Cantidad de compradores públicos distintos",
            "accent": "purple",
        },
        {
            "label": "Monto típico",
            "value": formato_soles(_montos_publicados.median()) if len(_montos_publicados) else "—",
            "note": _nota_montos,
            "accent": "blue",
        },
    ])

    if mostrar.empty:
        if solo_con_docs:
            st.info(
                "Ningún llamado vigente tiene documentos descargados. Es lo esperable: "
                "la documentación completa aparece cuando el proceso avanza, así que vive "
                "en llamados ya cerrados. Para ver documentos reales, entra al Paso 3 y "
                "abre «Ver un llamado con documentos publicados por la entidad»."
            )
        else:
            # Caso frecuente y confuso: el rubro tiene llamados abiertos pero
            # ninguno coincide con la descripción CUBSO exacta. Sin nombrarlo,
            # la pantalla parece contradecir al gráfico de rubros de arriba.
            sin_categoria = vigentes.copy()
            if rubro_elegido:
                sin_categoria = sin_categoria[
                    mascara_rubros(sin_categoria["cubso_descripcion"], [rubro_elegido])
                ]
            if solo_urgentes:
                sin_categoria = sin_categoria[sin_categoria["vigencia"] == "POR CERRAR"]

            if filtrar_categoria and st.session_state.categoria and not sin_categoria.empty:
                otras = ", ".join(
                    sorted(sin_categoria["cubso_descripcion"].dropna().astype(str).unique())[:3]
                )
                st.info(
                    f"Ningún llamado abierto es exactamente **{st.session_state.categoria}**, "
                    f"pero hay **{len(sin_categoria)}** en tu rubro. Desmarca «Solo la categoría "
                    f"exacta que elegí» para verlos.\n\n"
                    f"Categorías disponibles ahora: {otras}."
                )
            else:
                st.info(
                    "No hay llamados abiertos con estos filtros. Puedes quitar el filtro de "
                    "categoría o el de rubro para revisar otras oportunidades vigentes."
                )
        st.stop()

    st.markdown("#### Los que requieren atención primero")
    st.caption("Mostramos primero los llamados cuya fecha de cierre está más cerca.")
    render_llamados_destacados(mostrar)

    q("Q3", "¿Cuánto tiempo me queda y qué entidad está comprando?")
    ventana = mostrar.copy()
    ventana["Cierra en (días)"] = ventana["dias_para_cierre"].clip(lower=0)
    chart_ventana = (
        alt.Chart(ventana)
        .mark_circle(opacity=0.85, strokeWidth=2, stroke="white")
        .encode(
            x=alt.X(
                "Cierra en (días):Q",
                title="Días que quedan para presentar oferta",
                axis=alt.Axis(
                    gridColor="#E8ECF1",
                    labelColor=APAGADO,
                    titleColor=TINTA,
                    titleFontSize=13,
                    titleFontWeight=700,
                    labelFontSize=11,
                ),
            ),
            y=alt.Y(
                "entidad:N",
                title=None,
                axis=alt.Axis(
                    labelColor=TINTA,
                    labelFontSize=11,
                    labelFontWeight=600,
                ),
            ),
            size=alt.Size(
                "monto_referencial:Q",
                title="Monto referencial",
                scale=alt.Scale(range=[90, 620]),
            ),
            color=alt.Color(
                "vigencia:N",
                scale=alt.Scale(
                    domain=["POR CERRAR", "VIGENTE"],
                    range=[NARANJA, MORADO],
                ),
                legend=alt.Legend(
                    orient="bottom",
                    title=None,
                    labelFontSize=12,
                    labelFontWeight=700,
                    padding=15,
                ),
            ),
            tooltip=[
                alt.Tooltip("titulo:N", title="Llamado"),
                alt.Tooltip("entidad:N", title="Entidad"),
                alt.Tooltip("metodo_contratacion:N", title="Método"),
                alt.Tooltip("monto_referencial:Q", title="Monto", format=",.0f"),
                alt.Tooltip("dias_para_cierre:Q", title="Días restantes", format=".0f"),
            ],
        )
        .properties(height=320)
        .configure_view(strokeWidth=0, fill="transparent")
        .configure_axis(
            gridColor="#E8ECF1",
            labelColor=APAGADO,
            titleColor=TINTA,
        )
        .configure_legend(labelColor=APAGADO)
    )
    st.altair_chart(chart_ventana, use_container_width=True)

    lista, panel = st.columns([1.55, 0.9], gap="large")

    with lista:
        st.markdown("#### Oportunidades abiertas")
        for _, f in mostrar.sort_values("dias_para_cierre").head(30).iterrows():
            urgente = f["vigencia"] == "POR CERRAR"
            dias = numero_seguro(f.get("dias_para_cierre"), default=np.nan)
            monto = numero_seguro(f.get("monto_referencial"))

            st.markdown(
                f'<div class="ro-ancla" id="{ancla_llamado(f.get("ocid"))}"></div>',
                unsafe_allow_html=True,
            )
            with st.container(border=True):
                n_docs = int(DOCS_POR_OCID.get(str(f["ocid"]), 0))
                a, b, c = st.columns([4.2, 1.2, 1.35])
                with a:
                    st.markdown(
                        f"**{texto_seguro(f.get('titulo'))}**",
                        unsafe_allow_html=True,
                    )
                    marca_docs = (
                        f" · 📎 {n_docs} documento{'s' if n_docs != 1 else ''} publicados"
                        if n_docs else " · sin documentos en la descarga"
                    )
                    st.caption(
                        f"{f.get('entidad', '—')} · "
                        f"{f.get('metodo_contratacion', '—')} · "
                        f"{f.get('cubso_descripcion', '—')}"
                        f"{marca_docs}"
                    )
                with b:
                    dias_txt, dias_lbl, vencido = plazo_declarado(
                        dias, f.get("origen_limite")
                    )
                    color_dias = GRIS if vencido else NARANJA
                    tam_dias = "20" if len(dias_txt) > 4 else "27"
                    st.markdown(
                        f"<div style='font-size:{tam_dias}px;font-weight:880;"
                        f"color:{color_dias};line-height:1.1'>{escape(dias_txt)}</div>"
                        f"<div style='font-size:9.5px;color:{APAGADO};font-weight:750;margin-top:5px'>{escape(dias_lbl)}</div>",
                        unsafe_allow_html=True,
                    )
                with c:
                    monto_txt, monto_nota = monto_declarado(f)
                    color_monto = AZUL if monto > 0 else APAGADO
                    tam_monto = "16" if monto <= 0 else "19"
                    st.markdown(
                        f"<div style='font-size:{tam_monto}px;font-weight:850;"
                        f"color:{color_monto}'>{escape(monto_txt)}</div>"
                        # La nota puede contener el <abbr> de sigla("UIT"), así que
                        # va sin escape; los textos alternativos son planos.
                        f"<div style='font-size:11px;color:{APAGADO}'>{monto_nota}</div>",
                        unsafe_allow_html=True,
                    )
                    st.button(
                        "Ver requisitos →",
                        key=f"btn_{f['ocid']}",
                        type="primary" if urgente else "secondary",
                        use_container_width=True,
                        on_click=ir_a,
                        args=(PANTALLAS[2],),
                        kwargs={"ocid": f["ocid"]},
                    )

    with panel:
        q("Q3", "¿Quién está comprando ahora?")
        por_entidad = (
            mostrar.groupby("entidad")
            .size()
            .reset_index(name="Llamados")
            .sort_values("Llamados", ascending=False)
        )
        st.altair_chart(
            alt.Chart(por_entidad.head(10))
            .mark_bar(color=AZUL, cornerRadiusEnd=3)
            .encode(
                x=alt.X("Llamados:Q", title=None),
                # labelLimit amplio para que el nombre de la entidad no se
                # corte; cuando aun asi no entra, el tooltip lo muestra entero.
                y=alt.Y(
                    "entidad:N",
                    sort="-x",
                    title=None,
                    axis=alt.Axis(labelLimit=260, labelFontSize=10.5),
                ),
                tooltip=[
                    alt.Tooltip("entidad:N", title="Entidad"),
                    alt.Tooltip("Llamados:Q", title="Llamados"),
                ],
            )
            .properties(height=260)
            .configure_view(strokeWidth=0)
            .configure_axis(grid=False, labelColor=APAGADO),
            use_container_width=True,
        )

        q("Q4", "¿Qué tipo de proceso aparece con más frecuencia?")
        por_metodo = (
            mostrar.groupby("metodo_contratacion")
            .size()
            .reset_index(name="Llamados")
            .sort_values("Llamados", ascending=False)
        )
        st.altair_chart(
            alt.Chart(por_metodo)
            .mark_bar(color=MORADO, cornerRadiusEnd=3)
            .encode(
                x=alt.X("Llamados:Q", title=None),
                y=alt.Y(
                    "metodo_contratacion:N",
                    sort="-x",
                    title=None,
                    axis=alt.Axis(labelLimit=260, labelFontSize=10.5),
                ),
                tooltip=[
                    alt.Tooltip("metodo_contratacion:N", title="Procedimiento"),
                    alt.Tooltip("Llamados:Q", title="Llamados"),
                ],
            )
            .properties(height=210)
            .configure_view(strokeWidth=0)
            .configure_axis(grid=False, labelColor=APAGADO),
            use_container_width=True,
        )
        st.caption(
            "Este gráfico ayuda a reconocer qué procedimiento aparece más entre las oportunidades que estás revisando."
        )

    # El rubro marcado en el Paso 1 acompaña al Paso 2. Los llamados vigentes
    # son pocos por el desfase de la fuente; los cerrados del mismo rubro son
    # la referencia concreta de qué pide el Estado en ese giro.
    rubros_paso1 = st.session_state.get("rubros_paso1") or []
    if rubros_elegido_historial := ([rubro_elegido] if rubro_elegido else rubros_paso1):
        st.markdown('<hr class="ro-divider">', unsafe_allow_html=True)
        render_historial_rubro(convocatorias, rubros_elegido_historial)
    else:
        st.markdown('<hr class="ro-divider">', unsafe_allow_html=True)
        st.info(
            "Marca tu rubro en el Paso 1 (o toca una barra del gráfico de arriba) "
            "para ver los llamados anteriores de tu giro con el detalle de lo que "
            "pidió cada entidad."
        )


# ===========================================================================
# PANTALLA 3 — QUÉ TENGO QUE PREPARAR
# ===========================================================================
elif pantalla.startswith("3"):
    titulo_paso(
        "PASO 3 · PREPARAR LA POSTULACIÓN",
        "Antes de postular, revisa que no te falte nada",
        "Esta pantalla junta en un solo lugar las fechas, documentos y condiciones del llamado que elegiste.",
    )
    render_formalidades_cards()
    st.markdown(
        f"<div style='font-weight:850;color:{NARANJA};font-size:14px;margin-bottom:12px'>El radar no promete que vas a ganar. Su trabajo es ayudarte a elegir mejor y evitar perder una oportunidad por llegar tarde o con documentos incompletos.</div>",
        unsafe_allow_html=True,
    )

    catalogo = cargar_catalogo()

    conv = None
    if convocatorias is not None and st.session_state.ocid:
        fila_conv = convocatorias[
            convocatorias["ocid"] == st.session_state.ocid
        ]
        conv = fila_conv.iloc[0] if not fila_conv.empty else None

    if conv is None:
        st.info(
            "Elige un llamado en el Paso 2 para ver sus datos específicos. "
            "Mientras tanto, aquí aparecen los requisitos generales del catálogo del proyecto."
        )

    if conv is not None:
        if st.session_state.ocid_checklist != conv["ocid"]:
            st.session_state.listos = set()
            st.session_state.ocid_checklist = conv["ocid"]

        monto_conv = numero_seguro(conv.get("monto_referencial"))
        dias_conv = numero_seguro(
            conv.get("dias_para_cierre"), default=np.nan
        )
        dias_conv_txt = "—" if pd.isna(dias_conv) else f"{dias_conv:.0f} días"
        estado_conv = texto_seguro(conv.get("vigencia"))
        chip_plazo = (
            f"cierra en {escape(dias_conv_txt)}"
            if (not pd.isna(dias_conv) and dias_conv >= 0)
            else f"estado en el snapshot: {escape(estado_conv)}"
        )

        st.markdown(
            f"""
            <div class="ro-focus-head" style="background:{AZUL};border-color:{AZUL};color:#fff">
              <div>
                <div style="font-size:10px;color:#BBD0DE;font-weight:800;letter-spacing:.05em">LLAMADO QUE ESTÁS REVISANDO</div>
                <div style="font-size:19px;font-weight:850;color:#fff;line-height:1.25;margin-top:4px">{texto_seguro(conv.get('titulo'))}</div>
                <div style="font-size:12px;color:#C8D9E4;margin-top:6px">{texto_seguro(conv.get('entidad'))} · {texto_seguro(conv.get('metodo_contratacion'))} · {texto_seguro(conv.get('cubso_descripcion'))}</div>
              </div>
              <div style="margin-left:auto;display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end">
                <div class="ro-chip">{escape(formato_soles(monto_conv))}</div>
                <div class="ro-chip">{monto_conv/config.UIT_SOLES:,.0f} {sigla("UIT")}</div>
                <div class="ro-chip">{chip_plazo}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if conv is not None and cronograma is not None:
        hitos = cronograma[cronograma["ocid"] == conv["ocid"]].copy()
        if not hitos.empty:
            st.markdown("#### Fechas que no puedes dejar pasar")
            ahora = pd.Timestamp.now(tz="UTC")
            hitos = hitos.sort_values("fecha_programada")
            hitos["Días restantes"] = (
                (hitos["fecha_programada"] - ahora).dt.total_seconds() / 86400
            ).round(0)
            hitos["Estado"] = np.where(
                hitos["Días restantes"] < 0, "Vencido", "Pendiente"
            )
            linea = alt.Chart(hitos).mark_point(
                size=260, filled=True
            ).encode(
                x=alt.X("fecha_programada:T", title=None),
                color=alt.Color(
                    "Estado:N",
                    scale=alt.Scale(
                        domain=["Vencido", "Pendiente"],
                        range=["#C3CEDB", AZUL],
                    ),
                    legend=alt.Legend(orient="bottom", title=None),
                ),
                tooltip=["hito", "fecha_programada:T", "Días restantes"],
            )
            texto_hito = linea.mark_text(
                dy=-22, fontSize=12, color=TINTA
            ).encode(text="hito:N")
            hoy = alt.Chart(
                pd.DataFrame({"hoy": [ahora]})
            ).mark_rule(
                color=NARANJA, strokeDash=[4, 3]
            ).encode(x="hoy:T")
            st.altair_chart(
                (linea + texto_hito + hoy)
                .properties(height=150)
                .configure_view(strokeWidth=0)
                .configure_axis(grid=False, labelColor=APAGADO),
                use_container_width=True,
            )
            st.caption(
                "La línea naranja marca hoy. Así puedes ver rápidamente qué fecha viene después."
            )

    tipo_objeto = conv["tipo_objeto"] if conv is not None else None
    reqs = requisitos_por_objeto(catalogo, tipo_objeto)
    etapas = {e["clave"]: e for e in catalogo["etapas"]}
    total = len(reqs)
    listos = st.session_state.listos

    cab1, cab2 = st.columns([3, 1])
    cab1.markdown("#### Mi checklist para postular")
    cab2.progress(
        len(listos) / total if total else 0,
        text=f"{len(listos)} de {total} listos",
    )

    izq, der = st.columns([1.5, 1], gap="large")
    with izq:
        for clave in [
            e["clave"]
            for e in sorted(catalogo["etapas"], key=lambda x: x["orden"])
        ]:
            bloque = reqs[reqs["etapa"] == clave]
            if bloque.empty:
                continue
            st.markdown(f"**{etapas[clave]['nombre']}**")
            st.caption(etapas[clave]["resumen"])
            for _, r in bloque.iterrows():
                marcado = st.checkbox(
                    f"{'⚠️ ' if r['critico'] else ''}{r['requisito']}",
                    value=r["id"] in listos,
                    key=f"chk_{r['id']}",
                )
                if marcado:
                    listos.add(r["id"])
                else:
                    listos.discard(r["id"])
                with st.expander("¿Qué significa y cuál es la base legal?"):
                    st.write(r["detalle"])
                    st.caption(f"Base legal: {r['base_legal']}")

    with der:
        st.markdown("**Documentos que publicó la entidad**")
        docs = (
            documentos[documentos["ocid"] == conv["ocid"]]
            if (conv is not None and documentos is not None)
            else pd.DataFrame()
        )
        if docs.empty:
            st.markdown(
                '<div class="ro-aviso">En este llamado la entidad todavía no ha publicado '
                'documentos en la fuente consultada. Sin las bases no se pueden conocer los '
                'requisitos específicos, pero sí puedes revisar qué pidieron otras entidades '
                'en llamados parecidos.</div>',
                unsafe_allow_html=True,
            )

            categoria_ref = (
                conv.get("cubso_descripcion") if conv is not None
                else st.session_state.categoria
            )
            objeto_ref = conv.get("tipo_objeto") if conv is not None else None
            similares = candidatos_similares(categoria_ref, objeto_ref)

            if similares.empty:
                st.caption(
                    "La descarga tampoco tiene documentos de llamados parecidos. "
                    "Cuando estén disponibles, aquí podrás revisar:"
                )
            else:
                st.markdown("**Documentos de llamados similares**")
                st.caption(
                    "Elige uno para ver qué documentación pidió la entidad. "
                    "Están ordenados por parecido con tu categoría; varios ya cerraron, "
                    "porque la fuente entrega el expediente completo cuando el proceso avanza."
                )

                def _etiqueta_similar(ocid: str) -> str:
                    f = similares[similares["ocid"].astype(str) == str(ocid)].iloc[0]
                    marca = f"{int(f['n_documentos'])} doc."
                    if int(f["n_bases"]):
                        marca += f" · {int(f['n_bases'])} bases"
                    titulo_corto = texto_seguro(f.get("cubso_descripcion"))
                    if titulo_corto == "—":
                        titulo_corto = texto_seguro(f.get("titulo"))
                    return f"[{f['parecido']}] {titulo_corto} · {marca}"

                elegido = st.selectbox(
                    "Llamados similares con documentación",
                    similares["ocid"].astype(str).tolist(),
                    format_func=_etiqueta_similar,
                    key="sel_similar_docs",
                    label_visibility="collapsed",
                )
                detalle_sim = similares[
                    similares["ocid"].astype(str) == str(elegido)
                ].iloc[0]
                st.caption(
                    f"{texto_seguro(detalle_sim.get('entidad'))} · "
                    f"{texto_seguro(detalle_sim.get('titulo'))}"
                )
                st.button(
                    "Ver los documentos de este llamado →",
                    type="primary",
                    use_container_width=True,
                    on_click=ir_a,
                    args=(PANTALLAS[2],),
                    kwargs={"ocid": elegido},
                    key="btn_ver_similar_docs",
                )
                st.caption("Cuando publiquen los de tu llamado, aquí podrás revisar:")

            for _, meta in catalogo["tipos_documento_ocds"].items():
                with st.container(border=True):
                    st.markdown(f"**{meta['nombre']}**")
                    st.caption(meta.get("por_que_importa", ""))
        else:
            st.caption(
                f"{len(docs)} documento{'s' if len(docs) != 1 else ''} publicados por la "
                "entidad en la fuente consultada. Descárgalos y contrástalos con el checklist."
            )
            tipos = catalogo["tipos_documento_ocds"]
            for _, d in docs.iterrows():
                meta = tipos.get(d["tipo_documento"], {})
                with st.container(border=True):
                    st.markdown(
                        f"**{d['titulo']}** · "
                        f"{meta.get('nombre', d['tipo_documento'])}"
                    )
                    if meta.get("por_que_importa"):
                        st.caption(meta["por_que_importa"])
                    if pd.notna(d["url"]):
                        st.markdown(f"[Abrir documento]({d['url']})")

        st.markdown("**Normas usadas como referencia**")
        for norma in catalogo["marco_legal"]:
            st.markdown(
                f"- **{norma['norma']}** — {norma['nota']} "
                f"([fuente]({norma['url']}))"
            )
        st.warning(catalogo["advertencia"])


# ===========================================================================
# FUENTES Y ACTUALIZACIÓN
# ===========================================================================
else:
    titulo_paso(
        "FUENTES Y ACTUALIZACIÓN",
        "De dónde sale cada número y cuándo se actualizó",
        "Esta hoja final deja visible el periodo analizado, las fuentes usadas y la fecha detectada para cada corrida.",
    )

    st.markdown(
        f"""
        <div class="ro-period">
          <div class="ro-period-title">Periodo histórico seleccionado</div>
          <div class="ro-period-copy"><b>{escape(periodo_txt)}</b>. Este periodo alimenta demanda, ganadores históricos, ticket, estacionalidad, ranking e índice.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### El índice explicado sin fórmulas complicadas")
    st.markdown(
        f"""
        <div class="ro-index-help">
          <h4>¿Para qué sirve?</h4>
          <p>Sirve para <strong>ordenar categorías y decidir cuál revisar primero</strong>. No predice que vas a ganar una licitación.</p>
          <p><strong>Paso 1:</strong> damos 55% de peso a cuánto compró el Estado y 45% a cuánto espacio queda frente a los ganadores que siguen habilitados.</p>
          <p><strong>Paso 2:</strong> convertimos ambas señales a una escala comparable entre 0 y 1.</p>
          <p><strong>Paso 3:</strong> ajustamos el resultado por el tamaño promedio del contrato. Un contrato pequeño conserva más puntaje; uno muy grande recibe un castigo porque puede ser difícil para una {sigla("MYPE")}.</p>
          <p><strong>Resultado:</strong> un puntaje de 0 a 100 que se recalcula cuando cambias el periodo o los filtros.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Qué responde cada pregunta")
    st.dataframe(
        pd.DataFrame([
            {
                "Pregunta": "Q1 · ¿Dónde compra más el Estado?",
                "Qué mira": "Monto adjudicado en el periodo elegido",
                "Fuente": "OCDS / SEACE",
            },
            {
                "Pregunta": "Q2 · ¿Dónde tengo menos competencia conocida?",
                "Qué mira": "Ganadores del periodo que siguen habilitados hoy",
                "Fuente": "OCDS × RNP",
            },
            {
                "Pregunta": "Q3 · ¿Cuándo se mueve más la compra?",
                "Qué mira": "Mes con mayor monto y meses con actividad",
                "Fuente": "OCDS",
            },
            {
                "Pregunta": "Q4 · ¿El tamaño del contrato está a mi alcance?",
                "Qué mira": "Contrato promedio en soles y UIT",
                "Fuente": "OCDS + UIT vigente del proyecto",
            },
            {
                "Pregunta": "Q5 · ¿Cuántos siguen realmente en carrera?",
                "Qué mira": "Ganaron en el periodo → siguen habilitados hoy",
                "Fuente": "OCDS × RNP",
            },
        ]),
        width="stretch",
        hide_index=True,
    )

    st.markdown("### Siglas que aparecen en el dashboard")
    glosario_html = "".join(
        f'<div class="ro-glossary-item"><b>{escape(k)}</b><br><span>{escape(v)}</span></div>'
        for k, v in SIGLAS.items()
    )
    st.markdown(
        '<div class="ro-glossary">' + glosario_html + '</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Además, en los textos del dashboard puedes pasar el mouse sobre una sigla subrayada con puntos para ver su significado."
    )

    st.markdown("### Fuentes integradas")
    st.markdown(
        f"""
        | Fuente | Qué aporta al usuario |
        |---|---|
        | {sigla("OCDS")} / {sigla("SEACE")} | Compras históricas, montos, fechas y proveedores que ganaron |
        | {sigla("RNP")} | Permite saber si los ganadores históricos siguen habilitados |
        | Snapshot anual {sigla("OCDS")} del {sigla("OECE")} | Última cobertura disponible de procedimientos y fechas; puede tener desfase |
        | Buscadores públicos del {sigla("SEACE")} | Confirmación operativa de procedimientos vigentes antes de postular |
        | Catálogo de formalidades | Documentos, etapas y referencias normativas para preparar la postulación |
        | Diccionario {sigla("CUBSO")} | Relaciona la categoría de compra con la clasificación usada por el proyecto |
        """,
        unsafe_allow_html=True,
    )

    if convocatorias is not None and not convocatorias.empty:
        st.markdown("### Una precisión sobre las fechas del snapshot")
        st.markdown(
            f"""
            <div class="ro-aviso">
            El Parquet de convocatorias trae dos fechas y solo una sirve para medir actividad.
            <b>fecha_publicacion</b> guarda el instante en que el pipeline {sigla("OCDS")} del
            {sigla("OECE")} escribió el registro: concentra miles de filas en domingos y fecha
            en 2026 procedimientos convocados en 2014. <b>fecha_inicio_ofertas</b>
            (<i>tenderPeriod.startDate</i>) sí reproduce el calendario administrativo, con
            cientos de convocatorias por día hábil y ninguna en fines de semana ni feriados.
            El dashboard usa esta última; {_sin_fecha_convocatoria:,} de
            {len(convocatorias):,} registros no la traen y quedan fuera de ese conteo.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Fecha de cada corrida")
    corridas = pd.DataFrame([
        {
            "Proceso / dato": "Compras históricas OCDS",
            "Última corrida detectada": ultima_corrida(["ingesta_ocds"]),
            "Qué actualiza": "Detalle histórico de adjudicaciones",
        },
        {
            "Proceso / dato": "Estado de proveedores RNP",
            "Última corrida detectada": ultima_corrida(["ficha_proveedores"]),
            "Qué actualiza": "Habilitación de los proveedores consultados",
        },
        {
            "Proceso / dato": "Cruce de competencia",
            "Última corrida detectada": ultima_corrida(["consulta_proveedores"]),
            "Qué actualiza": "Ganadores del histórico que siguen habilitados",
        },
        {
            "Proceso / dato": "Snapshot de procedimientos OECE",
            "Última corrida detectada": ultima_corrida(["monitor_convocatorias"]),
            "Qué actualiza": "Última cobertura disponible de procedimientos, montos y fechas",
        },
        {
            "Proceso / dato": "Integración e índice",
            "Última corrida detectada": ultima_corrida(["diagnostico", "transformacion"]),
            "Qué actualiza": "Dataset maestro, bandas e índice de oportunidad",
        },
        {
            "Proceso / dato": "Formalidades",
            "Última corrida detectada": ultima_corrida(["formalidades"]),
            "Qué actualiza": "Checklist y catálogo normativo del proyecto",
        },
    ])
    st.dataframe(corridas, width="stretch", hide_index=True)

    if ocds_periodo is not None and not ocds_periodo.empty:
        fechas_validas = pd.to_datetime(
            ocds_periodo["fecha"], errors="coerce", utc=True
        ).dropna()
        if not fechas_validas.empty:
            st.caption(
                "Rango efectivo de registros históricos dentro del filtro: "
                f"{fechas_validas.min().strftime('%d/%m/%Y')} a "
                f"{fechas_validas.max().strftime('%d/%m/%Y')}."
            )

    st.info(
        "Importante: los filtros de año y mes cambian el histórico y recalculan el índice. "
        "La última descarga de procedimientos puede tener desfase respecto del SEACE. "
        "Para decidir qué puedes postular hoy, confirma la vigencia directamente en los buscadores públicos del SEACE."
    )
