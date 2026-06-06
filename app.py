#!/usr/bin/env python3
"""
SmartCAT.AI — Slip Extraction UI (EXL).

Upload insurance slips (PDF, Word, scanned images) and extract TIV, limits,
sublimits, deductibles, participation, SIR, waiting periods, and CAT perils.
"""
from __future__ import annotations

from contextlib import contextmanager
import logging
import os
import time
import traceback
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from modules.module3_slip_extraction import SlipExtractionEngine
from smartcat_logging import setup_logging
from smartcat_paths import OUTPUT_DIR, PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")

setup_logging()
log = logging.getLogger("smartcat.app")

OUT_SLIP = OUTPUT_DIR / "extracted_slips"
TMP_SLIPS = OUTPUT_DIR / "_tmp_slips"

ACCEPT_TYPES = ["pdf", "docx", "png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp"]

# EXL Planet / iPlanet portal palette
EXL_ORANGE = "#E84E0E"
EXL_ORANGE_DARK = "#C7410B"
EXL_ORANGE_LIGHT = "#FFF3EE"
EXL_BLACK = "#222222"
EXL_GREY_DARK = "#555555"
EXL_GREY_MID = "#888888"
EXL_GREY_LIGHT = "#DEDEDE"
EXL_GREY_NAV = "#EBEBEB"
EXL_GREY_BG = "#F2F2F2"
EXL_GREY_SECTION = "#E8E8E8"
EXL_WHITE = "#FFFFFF"


def _init_session() -> None:
    defaults = {
        "slip_upload_nonce": 0,
        "slip_completed": False,
        "slip_error": None,
        "slip_traceback": None,
        "slip_records": [],
        "slip_paths": {},
        "slip_stats": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _inject_exl_styles() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        section[data-testid="stSidebar"] {{ display: none !important; }}
        div[data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}
        header[data-testid="stHeader"] {{
            background: {EXL_WHITE} !important;
            border-bottom: none !important;
            height: 0 !important;
            min-height: 0 !important;
            visibility: hidden !important;
            overflow: hidden !important;
        }}
        #MainMenu, footer {{ visibility: hidden; }}
        [data-testid="stToolbar"] {{
            display: none !important;
        }}

        /* Force light theme CSS vars (Streamlit Cloud dark-theme override) */
        :root {{
            --background-color: {EXL_GREY_BG} !important;
            --secondary-background-color: {EXL_WHITE} !important;
            --text-color: {EXL_BLACK} !important;
            --primary-color: {EXL_ORANGE} !important;
        }}
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], .main {{
            background-color: {EXL_GREY_BG} !important;
            color: {EXL_BLACK} !important;
        }}

        html, body, [class*="css"] {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }}

        .stApp {{
            background: {EXL_GREY_BG};
            color: {EXL_BLACK};
        }}

        .block-container {{
            padding-top: 0 !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            padding-bottom: 2rem !important;
            max-width: 1080px !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }}
        [data-testid="stMainBlockContainer"] {{
            padding-top: 0 !important;
        }}

        /* Unified page shell — header + sections share same width */
        .exl-site-header {{
            background: {EXL_WHITE};
            border: 1px solid {EXL_GREY_LIGHT};
            border-radius: 8px;
            margin-bottom: 1.25rem;
            margin-top: 0.35rem;
            overflow: visible;
        }}

        /* ── Animations ── */
        @keyframes exlFadeInUp {{
            from {{ opacity: 0; transform: translateY(18px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        @keyframes exlFadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        @keyframes exlSlideIn {{
            from {{ opacity: 0; transform: translateX(-12px); }}
            to {{ opacity: 1; transform: translateX(0); }}
        }}
        @keyframes exlPulse {{
            0%, 100% {{ transform: scale(1); box-shadow: 0 0 0 0 rgba(232,78,14,0.45); }}
            50% {{ transform: scale(1.08); box-shadow: 0 0 0 6px rgba(232,78,14,0); }}
        }}
        @keyframes exlGradientShift {{
            0% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
            100% {{ background-position: 0% 50%; }}
        }}
        @keyframes exlRowIn {{
            from {{ opacity: 0; transform: translateX(-6px); }}
            to {{ opacity: 1; transform: translateX(0); }}
        }}
        @keyframes exlShine {{
            0% {{ left: -100%; }}
            100% {{ left: 200%; }}
        }}

        .exl-animate-in {{
            animation: exlFadeInUp 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
        }}
        .exl-animate-in-slow {{
            animation: exlFadeInUp 0.75s cubic-bezier(0.22, 1, 0.36, 1) both;
        }}
        .exl-topbar {{
            animation: exlFadeIn 0.45s ease-out both;
        }}
        .exl-navstrip {{
            animation: exlSlideIn 0.5s ease-out 0.05s both;
        }}
        .exl-hero {{
            animation: exlFadeInUp 0.6s cubic-bezier(0.22, 1, 0.36, 1) 0.08s both;
        }}
        .exl-section {{
            animation: exlFadeInUp 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
        }}
        .exl-metric {{
            animation: exlFadeInUp 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
            transition: transform 0.25s ease, box-shadow 0.25s ease;
        }}
        .exl-metric:nth-child(1) {{ animation-delay: 0.05s; }}
        .exl-metric:nth-child(2) {{ animation-delay: 0.12s; }}
        .exl-metric:nth-child(3) {{ animation-delay: 0.19s; }}
        .exl-metric:nth-child(4) {{ animation-delay: 0.26s; }}
        .exl-metric:hover {{
            transform: translateY(-3px);
            box-shadow: 0 8px 22px rgba(232,78,14,0.12);
        }}
        .exl-success-banner {{
            animation: exlFadeInUp 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
        }}
        .exl-data-table {{
            animation: exlFadeInUp 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;
        }}
        .exl-data-table tbody tr {{
            animation: exlRowIn 0.35s ease-out both;
        }}
        .exl-data-table tbody tr:nth-child(1) {{ animation-delay: 0.03s; }}
        .exl-data-table tbody tr:nth-child(2) {{ animation-delay: 0.06s; }}
        .exl-data-table tbody tr:nth-child(3) {{ animation-delay: 0.09s; }}
        .exl-data-table tbody tr:nth-child(4) {{ animation-delay: 0.12s; }}
        .exl-data-table tbody tr:nth-child(5) {{ animation-delay: 0.15s; }}
        .exl-data-table tbody tr:nth-child(n+6) {{ animation-delay: 0.18s; }}
        .exl-tab-panel {{
            animation: exlFadeInUp 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
        }}

        /* ── Header (Planet EXL style) ── */
        .exl-topbar {{
            background: {EXL_WHITE};
            margin: 0;
            padding: 0.95rem 1.5rem 0.85rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid {EXL_GREY_LIGHT};
        }}
        .exl-logo {{
            display: flex;
            align-items: baseline;
            gap: 6px;
            line-height: 1.25;
        }}
        .exl-logo-mark {{
            color: {EXL_ORANGE};
            font-weight: 800;
            font-size: 1.55rem;
            letter-spacing: -0.03em;
            line-height: 1.25;
            padding-top: 1px;
        }}
        .exl-logo-text {{
            color: {EXL_GREY_MID};
            font-weight: 600;
            font-size: 1.05rem;
            letter-spacing: -0.01em;
            line-height: 1.25;
        }}
        .exl-topbar-right {{
            text-align: right;
        }}
        .exl-built-by {{
            color: {EXL_ORANGE};
            font-size: 0.82rem;
            font-weight: 600;
        }}
        .exl-built-by span {{
            color: {EXL_GREY_MID};
            font-weight: 400;
        }}

        /* ── Nav strip ── */
        .exl-navstrip {{
            background: {EXL_GREY_NAV};
            margin: 0;
            padding: 0.55rem 1.5rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid {EXL_GREY_LIGHT};
        }}
        .exl-navstrip-links {{
            display: flex;
            gap: 1.5rem;
            font-size: 0.78rem;
            font-weight: 500;
            color: {EXL_GREY_DARK};
        }}
        .exl-navstrip-links .active {{
            color: {EXL_ORANGE};
            font-weight: 700;
        }}
        .exl-navstrip-tag {{
            font-size: 0.72rem;
            color: {EXL_GREY_MID};
            font-weight: 500;
        }}

        /* ── Hero ── */
        .exl-hero {{
            background: {EXL_WHITE};
            margin: 0;
            padding: 1.5rem 1.5rem 1.35rem;
        }}
        .exl-hero-tag {{
            display: inline-block;
            background: {EXL_GREY_SECTION};
            color: {EXL_GREY_DARK};
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            padding: 5px 12px;
            border-radius: 3px;
            margin-bottom: 0.75rem;
        }}
        .exl-hero h1 {{
            font-size: clamp(1.6rem, 3.5vw, 2.1rem);
            font-weight: 800;
            color: {EXL_BLACK};
            margin: 0 0 0.4rem;
            letter-spacing: -0.03em;
            line-height: 1.2;
        }}
        .exl-hero h1 span {{
            background: linear-gradient(120deg, {EXL_ORANGE}, #FF7040, {EXL_ORANGE_DARK}, {EXL_ORANGE});
            background-size: 250% auto;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            animation: exlGradientShift 5s ease infinite;
        }}
        .exl-hero p {{
            color: {EXL_GREY_DARK};
            font-size: 0.95rem;
            margin: 0;
            max-width: 640px;
            line-height: 1.55;
        }}

        /* Section card — symmetric horizontal inset for all body content */
        div[data-testid="stVerticalBlock"]:has(.exl-section-marker):not(
            :has(div[data-testid="stVerticalBlock"] .exl-section-marker)
        ) {{
            background: {EXL_WHITE} !important;
            border: 1px solid {EXL_GREY_LIGHT} !important;
            border-radius: 8px !important;
            margin-bottom: 1.25rem !important;
            padding: 0 1.25rem 1.25rem 1.25rem !important;
            overflow: hidden !important;
            animation: exlFadeInUp 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
            box-sizing: border-box !important;
        }}
        div[data-testid="stVerticalBlock"]:has(.exl-section-marker):not(
            :has(div[data-testid="stVerticalBlock"] .exl-section-marker)
        ) [data-testid="element-container"] {{
            padding-left: 0 !important;
            padding-right: 0 !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
        }}
        div[data-testid="stVerticalBlock"]:has(.exl-section-marker):not(
            :has(div[data-testid="stVerticalBlock"] .exl-section-marker)
        ) [data-testid="stButton"],
        div[data-testid="stVerticalBlock"]:has(.exl-section-marker):not(
            :has(div[data-testid="stVerticalBlock"] .exl-section-marker)
        ) [data-testid="stDownloadButton"],
        div[data-testid="stVerticalBlock"]:has(.exl-section-marker):not(
            :has(div[data-testid="stVerticalBlock"] .exl-section-marker)
        ) [data-testid="stFileUploader"],
        div[data-testid="stVerticalBlock"]:has(.exl-section-marker):not(
            :has(div[data-testid="stVerticalBlock"] .exl-section-marker)
        ) [data-testid="stCaptionContainer"],
        div[data-testid="stVerticalBlock"]:has(.exl-section-marker):not(
            :has(div[data-testid="stVerticalBlock"] .exl-section-marker)
        ) [data-testid="stMarkdownContainer"] {{
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
        }}
        div[data-testid="stVerticalBlock"]:has(.exl-section-marker):not(
            :has(div[data-testid="stVerticalBlock"] .exl-section-marker)
        ) [data-testid="stButton"] > button,
        div[data-testid="stVerticalBlock"]:has(.exl-section-marker):not(
            :has(div[data-testid="stVerticalBlock"] .exl-section-marker)
        ) [data-testid="stDownloadButton"] > button {{
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
        }}
        div[data-testid="stVerticalBlock"]:has(.exl-section-marker):not(
            :has(div[data-testid="stVerticalBlock"] .exl-section-marker)
        ) .exl-section-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
            margin: 0 -1.25rem 1.25rem -1.25rem;
            padding: 0.85rem 1.25rem 0.85rem 1rem;
            background: {EXL_GREY_SECTION};
            border-bottom: 1px solid {EXL_GREY_LIGHT};
            box-sizing: border-box;
        }}
        div[data-testid="stVerticalBlock"]:has(.exl-section-marker):not(
            :has(div[data-testid="stVerticalBlock"] .exl-section-marker)
        ) .exl-section-header .exl-section-sub {{
            padding-right: 0.25rem;
        }}
        .exl-section-header-stacked {{
            flex-direction: column;
            align-items: flex-start;
            gap: 0.35rem;
            padding: 0.85rem 1.25rem 0.85rem 1rem;
        }}
        .exl-section-header-row {{
            display: flex;
            align-items: center;
            gap: 10px;
            width: 100%;
        }}
        .exl-section-header-stacked .exl-section-sub {{
            margin-left: 36px;
            margin-top: 0;
            padding-left: 0;
            padding-right: 0;
            text-align: left;
        }}
        .exl-section-marker {{
            display: none !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }}
        .exl-section-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
            box-sizing: border-box;
        }}
        .exl-step-num {{
            background: {EXL_ORANGE};
            color: white;
            width: 26px;
            height: 26px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
            font-weight: 700;
            flex-shrink: 0;
        }}
        .exl-section-title {{
            font-size: 0.95rem;
            font-weight: 700;
            color: {EXL_BLACK};
            letter-spacing: -0.01em;
            flex: 1 1 auto;
            min-width: 0;
        }}
        .exl-section-sub {{
            font-size: 0.78rem;
            color: {EXL_GREY_MID};
            margin-left: auto;
            flex-shrink: 0;
            text-align: right;
            padding-right: 0;
        }}

        /* ── Metric cards ── */
        .exl-metrics {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin: 0.5rem 0 1rem;
        }}
        @media (max-width: 768px) {{
            .exl-metrics {{ grid-template-columns: repeat(2, 1fr); }}
        }}
        .exl-metric {{
            background: {EXL_WHITE};
            border: 1px solid {EXL_GREY_LIGHT};
            border-left: 3px solid {EXL_ORANGE};
            border-radius: 6px;
            padding: 0.85rem 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        .exl-metric-label {{
            font-size: 0.74rem;
            font-weight: 700;
            color: {EXL_BLACK};
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 6px;
            line-height: 1.3;
        }}
        .exl-metric-value {{
            font-size: 1.2rem;
            font-weight: 800;
            color: {EXL_BLACK};
            letter-spacing: -0.02em;
        }}
        .exl-conf-high {{ color: #0D7A3E !important; }}
        .exl-conf-mid {{ color: {EXL_ORANGE} !important; }}
        .exl-conf-low {{ color: #C0392B !important; }}

        .exl-slip-title {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 1rem;
            font-weight: 700;
            color: {EXL_BLACK};
            margin-bottom: 0.85rem;
            padding: 0.65rem 1rem;
            background: {EXL_WHITE};
            border: 1px solid {EXL_GREY_LIGHT};
            border-left: 4px solid {EXL_ORANGE};
            border-radius: 6px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        }}
        .exl-slip-title-icon {{
            font-size: 1.1rem;
        }}

        /* ── Detail panel ── */
        .exl-detail-panel {{
            background: {EXL_WHITE};
            border: 1px solid {EXL_GREY_LIGHT};
            border-radius: 6px;
            padding: 0.85rem 1.1rem;
            margin-top: 0.75rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            animation: exlFadeInUp 0.5s cubic-bezier(0.22, 1, 0.36, 1) 0.3s both;
        }}

        /* ── Success banner ── */
        .exl-success-banner {{
            background: {EXL_WHITE};
            border: 1px solid {EXL_GREY_LIGHT};
            border-left: 4px solid {EXL_ORANGE};
            border-radius: 6px;
            padding: 1rem 1.25rem;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .exl-success-dot {{
            width: 10px;
            height: 10px;
            background: {EXL_ORANGE};
            border-radius: 50%;
            flex-shrink: 0;
            animation: exlPulse 2.2s ease-in-out infinite;
        }}
        .exl-success-text {{
            font-size: 0.9rem;
            color: {EXL_GREY_DARK};
        }}
        .exl-success-text b {{
            color: {EXL_BLACK};
        }}

        /* ── Detail row ── */
        .exl-detail-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px 24px;
            margin-top: 0.5rem;
        }}
        @media (max-width: 768px) {{
            .exl-detail-grid {{ grid-template-columns: 1fr; }}
        }}
        .exl-detail-item {{
            font-size: 0.82rem;
            color: {EXL_GREY_DARK};
            line-height: 1.5;
        }}
        .exl-detail-item strong {{
            color: {EXL_BLACK};
            font-weight: 600;
        }}

        /* ── Footer ── */
        .exl-footer {{
            text-align: center;
            padding: 1.25rem 1.5rem 0.75rem;
            font-size: 0.75rem;
            color: {EXL_GREY_MID};
            border-top: 1px solid {EXL_GREY_LIGHT};
            margin-top: 2rem;
            background: {EXL_WHITE};
            border-radius: 8px;
            border: 1px solid {EXL_GREY_LIGHT};
        }}
        .exl-footer strong {{
            color: {EXL_ORANGE};
            font-weight: 700;
        }}
        .exl-footer-credit {{
            margin-top: 0.35rem;
            font-size: 0.78rem;
            color: {EXL_GREY_DARK};
        }}
        .exl-footer-credit b {{
            color: {EXL_ORANGE};
            font-weight: 600;
        }}

        /* ── File uploader dropzone (local + Streamlit Cloud) ── */
        div[data-testid="stFileUploader"] {{
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
        }}
        div[data-testid="stFileUploader"] section,
        div[data-testid="stFileUploader"] [data-testid="stFileUploadDropzone"],
        div[data-testid="stFileUploader"] [data-testid="stFileUploadDropzone"] > div,
        div[data-testid="stFileUploader"] [data-testid="stFileUploadDropzone"] div[data-testid="stVerticalBlock"] {{
            background-color: {EXL_GREY_LIGHT} !important;
            background: {EXL_GREY_LIGHT} !important;
        }}
        div[data-testid="stFileUploader"] section[data-testid="stFileUploadDropzone"] {{
            border: 1.5px dashed {EXL_GREY_MID} !important;
            border-radius: 8px !important;
            padding: 1.75rem 1.5rem !important;
            min-height: 110px !important;
            transition: border-color 0.2s, background 0.2s !important;
        }}
        div[data-testid="stFileUploader"] section[data-testid="stFileUploadDropzone"]:hover,
        div[data-testid="stFileUploader"] section[data-testid="stFileUploadDropzone"]:hover > div {{
            border-color: {EXL_ORANGE} !important;
            background-color: #EFEFEF !important;
            background: #EFEFEF !important;
        }}
        div[data-testid="stFileUploader"] [data-testid="stFileUploadDropzone"] span,
        div[data-testid="stFileUploader"] [data-testid="stFileUploadDropzone"] p,
        div[data-testid="stFileUploader"] [data-testid="stFileUploadDropzone"] label,
        div[data-testid="stFileUploader"] [data-testid="stFileUploadDropzone"] div {{
            color: {EXL_BLACK} !important;
        }}
        div[data-testid="stFileUploader"] section[data-testid="stFileUploadDropzone"] span,
        div[data-testid="stFileUploader"] section[data-testid="stFileUploadDropzone"] p {{
            font-size: 1.05rem !important;
            font-weight: 600 !important;
            line-height: 1.5 !important;
        }}
        div[data-testid="stFileUploader"] section[data-testid="stFileUploadDropzone"] small {{
            color: {EXL_GREY_DARK} !important;
            font-size: 0.88rem !important;
            font-weight: 500 !important;
            line-height: 1.6 !important;
            margin-top: 6px !important;
            display: block !important;
        }}
        div[data-testid="stFileUploader"] section[data-testid="stFileUploadDropzone"] svg,
        div[data-testid="stFileUploader"] [data-testid="stFileUploadDropzone"] svg {{
            stroke: {EXL_GREY_DARK} !important;
            fill: none !important;
            width: 28px !important;
            height: 28px !important;
        }}
        div[data-testid="stFileUploader"] section[data-testid="stFileUploadDropzone"] button,
        div[data-testid="stFileUploader"] [data-testid="stFileUploadDropzone"] button,
        div[data-testid="stFileUploader"] button {{
            background: {EXL_WHITE} !important;
            background-color: {EXL_WHITE} !important;
            color: {EXL_BLACK} !important;
            border: 1.5px solid {EXL_GREY_MID} !important;
            border-radius: 6px !important;
            font-size: 0.9rem !important;
            font-weight: 600 !important;
            padding: 0.45rem 1.1rem !important;
        }}
        div[data-testid="stFileUploader"] section[data-testid="stFileUploadDropzone"] button:hover,
        div[data-testid="stFileUploader"] [data-testid="stFileUploadDropzone"] button:hover,
        div[data-testid="stFileUploader"] button:hover {{
            border-color: {EXL_ORANGE} !important;
            color: {EXL_ORANGE} !important;
            background: {EXL_WHITE} !important;
            background-color: {EXL_WHITE} !important;
        }}
        /* Uploaded file list row */
        div[data-testid="stFileUploader"] [data-testid="stFileUploaderFileName"],
        div[data-testid="stFileUploader"] [data-testid="stFileUploaderFileName"] > div {{
            background: {EXL_WHITE} !important;
            color: {EXL_BLACK} !important;
        }}

        div[data-testid="stButton"] > button[kind="primary"] {{
            background: {EXL_ORANGE} !important;
            border: none !important;
            border-radius: 6px !important;
            font-weight: 700 !important;
            font-size: 0.9rem !important;
            letter-spacing: 0.02em !important;
            padding: 0.65rem 1.5rem !important;
            transition: background 0.2s, transform 0.2s, box-shadow 0.2s !important;
            box-shadow: 0 2px 8px rgba(240,90,40,0.25) !important;
            position: relative;
            overflow: hidden;
        }}
        div[data-testid="stButton"] > button[kind="primary"]::after {{
            content: "";
            position: absolute;
            top: 0;
            left: -100%;
            width: 60%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.25), transparent);
            animation: exlShine 3.5s ease-in-out infinite;
        }}
        div[data-testid="stButton"] > button[kind="primary"]:hover:not(:disabled) {{
            background: {EXL_ORANGE_DARK} !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 14px rgba(240,90,40,0.35) !important;
        }}
        div[data-testid="stButton"] > button[kind="primary"]:disabled {{
            background: {EXL_GREY_LIGHT} !important;
            color: {EXL_GREY_MID} !important;
            box-shadow: none !important;
        }}

        div[data-testid="stButton"] > button[kind="secondary"] {{
            border: 1px solid {EXL_GREY_LIGHT} !important;
            color: {EXL_GREY_DARK} !important;
            border-radius: 6px !important;
            font-weight: 600 !important;
            font-size: 0.82rem !important;
            background: {EXL_WHITE} !important;
        }}
        div[data-testid="stButton"] > button[kind="secondary"]:hover {{
            border-color: {EXL_ORANGE} !important;
            color: {EXL_ORANGE} !important;
        }}

        div[data-testid="stDownloadButton"] > button {{
            background: {EXL_ORANGE} !important;
            color: {EXL_WHITE} !important;
            border: none !important;
            border-radius: 4px !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
            transition: background 0.2s !important;
        }}
        div[data-testid="stDownloadButton"] > button:hover {{
            background: {EXL_ORANGE_DARK} !important;
        }}

        div[data-testid="stMetric"] {{
            background: {EXL_WHITE};
            border: 1px solid {EXL_GREY_LIGHT};
            border-left: 3px solid {EXL_ORANGE};
            border-radius: 6px;
            padding: 0.75rem 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        div[data-testid="stMetricLabel"],
        div[data-testid="stMetricLabel"] p,
        div[data-testid="stMetricLabel"] label,
        div[data-testid="stMetricLabel"] span {{
            font-size: 0.74rem !important;
            font-weight: 700 !important;
            color: {EXL_BLACK} !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
            opacity: 1 !important;
        }}
        div[data-testid="stMetricValue"],
        div[data-testid="stMetricValue"] div {{
            font-size: 1.2rem !important;
            font-weight: 800 !important;
            color: {EXL_BLACK} !important;
        }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 6px;
            background: {EXL_GREY_BG};
            border-radius: 10px;
            padding: 6px;
            border: 1px solid {EXL_GREY_LIGHT};
            margin-bottom: 0.75rem;
        }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 0.78rem !important;
            color: {EXL_GREY_DARK} !important;
            padding: 8px 14px !important;
            background: {EXL_WHITE} !important;
            border: 1px solid {EXL_GREY_LIGHT} !important;
            transition: all 0.2s ease !important;
        }}
        .stTabs [data-baseweb="tab"]:hover {{
            border-color: {EXL_ORANGE} !important;
            color: {EXL_ORANGE} !important;
        }}
        .stTabs [aria-selected="true"] {{
            background: {EXL_ORANGE} !important;
            color: {EXL_WHITE} !important;
            border-color: {EXL_ORANGE} !important;
            box-shadow: 0 4px 12px rgba(232,78,14,0.25) !important;
        }}
        .stTabs [data-baseweb="tab-panel"] {{
            padding-top: 0.5rem;
            animation: exlFadeInUp 0.35s ease-out both;
        }}

        div[data-testid="stExpander"] {{
            border: 1px solid {EXL_GREY_LIGHT} !important;
            border-radius: 8px !important;
            background: {EXL_WHITE} !important;
        }}

        div[data-testid="stStatus"] {{
            border: 1px solid {EXL_GREY_LIGHT};
            border-radius: 8px;
        }}

        .stAlert {{
            border-radius: 6px !important;
        }}

        hr {{
            border-color: {EXL_GREY_LIGHT} !important;
            margin: 1.25rem 0 !important;
        }}

        h3, h2 {{
            color: {EXL_BLACK} !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em !important;
        }}

        /* ── Data tables: HTML fallback for reliable display on themed deploys ── */
        div[data-testid="stDataFrame"] {{
            border: 1px solid {EXL_GREY_LIGHT};
            border-radius: 6px;
        }}
        .exl-data-table {{
            border: 1px solid {EXL_GREY_LIGHT};
            border-radius: 6px;
            overflow-x: auto;
            margin: 0.5rem 0 1rem;
            background: {EXL_WHITE};
        }}
        .exl-data-table table {{
            width: 100%;
            border-collapse: collapse;
            background: {EXL_WHITE} !important;
            color: {EXL_BLACK} !important;
            font-size: 0.84rem;
        }}
        .exl-data-table thead th {{
            background: {EXL_GREY_SECTION} !important;
            color: {EXL_BLACK} !important;
            font-weight: 700;
            font-size: 0.82rem;
            padding: 0.55rem 0.75rem;
            text-align: left;
            border-bottom: 2px solid {EXL_GREY_LIGHT};
            white-space: nowrap;
        }}
        .exl-data-table tbody td {{
            background: {EXL_WHITE} !important;
            color: {EXL_BLACK} !important;
            padding: 0.5rem 0.75rem;
            border-bottom: 1px solid {EXL_GREY_LIGHT};
            vertical-align: top;
        }}
        .exl-data-table tbody tr:nth-child(even) td {{
            background: {EXL_GREY_BG} !important;
        }}
        div[data-testid="stTable"] {{
            border: 1px solid {EXL_GREY_LIGHT};
            border-radius: 6px;
            overflow-x: auto;
        }}
        div[data-testid="stTable"] table {{
            background: {EXL_WHITE} !important;
            color: {EXL_BLACK} !important;
        }}
        div[data-testid="stTable"] thead th {{
            background: {EXL_GREY_SECTION} !important;
            color: {EXL_BLACK} !important;
            font-weight: 700 !important;
            font-size: 0.82rem !important;
            border-bottom: 2px solid {EXL_GREY_LIGHT} !important;
        }}
        div[data-testid="stTable"] tbody td {{
            background: {EXL_WHITE} !important;
            color: {EXL_BLACK} !important;
            font-size: 0.84rem !important;
            border-bottom: 1px solid {EXL_GREY_LIGHT} !important;
        }}
        div[data-testid="stTable"] tbody tr:nth-child(even) td {{
            background: {EXL_GREY_BG} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header() -> None:
    st.markdown(
        f"""
        <div class="exl-site-header">
            <div class="exl-topbar">
                <div class="exl-logo">
                    <div class="exl-logo-mark">EXL</div>
                    <div class="exl-logo-text">SmartCAT.AI</div>
                </div>
                <div class="exl-topbar-right">
                    <div class="exl-built-by">Built by <span>Satyam Mishra</span></div>
                </div>
            </div>
            <div class="exl-navstrip">
                <div class="exl-navstrip-links">
                    <span class="active">Slip Extraction</span>
                    <span>Insurance Intelligence</span>
                </div>
                <div class="exl-navstrip-tag">CAT Modelling · Slip Modelling</div>
            </div>
            <div class="exl-hero">
                <div class="exl-hero-tag">Slip Modelling &amp; Extraction</div>
                <h1>Smart<span>CAT</span>.AI</h1>
                <p>Extract TIV, limits, sublimits, deductibles, participation, SIR, waiting periods,
                and CAT peril terms from insurance slips — output to structured tables and Excel.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_section_header(step: int, title: str, subtitle: str = "") -> None:
    use_stacked = bool(subtitle) and len(subtitle) > 22
    if use_stacked:
        st.markdown(
            f"""
            <div class="exl-section-header exl-section-header-stacked">
                <div class="exl-section-header-row">
                    <div class="exl-step-num">{step}</div>
                    <div class="exl-section-title">{title}</div>
                </div>
                <div class="exl-section-sub">{subtitle}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    sub_html = f'<span class="exl-section-sub">{subtitle}</span>' if subtitle else ""
    st.markdown(
        f"""
        <div class="exl-section-header">
            <div class="exl-step-num">{step}</div>
            <div class="exl-section-title">{title}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _fmt_money(val: Any) -> str:
    if val is None or val == "":
        return "—"
    try:
        n = float(str(val).replace(",", ""))
        return f"${n:,.0f}"
    except ValueError:
        return str(val)


def _fmt_pct(val: Any) -> str:
    if val is None or val == "":
        return "—"
    try:
        return f"{float(val):g}%"
    except (TypeError, ValueError):
        return str(val)


MONEY_TABLE_COLS = frozenset({
    "amount", "min_amount", "max_amount", "primary_limit",
    "tiv", "limit_of_liability", "blanket_limit", "aggregate_limit",
})
PCT_TABLE_COLS = frozenset({"pct", "participation_pct", "coinsurance_pct"})


def _is_empty_val(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    s = str(val).strip().lower()
    return s in ("", "none", "nan", "—")


def _conf_class(score: Any) -> str:
    try:
        n = float(score)
    except (TypeError, ValueError):
        return "exl-conf-mid"
    if n >= 70:
        return "exl-conf-high"
    if n >= 40:
        return "exl-conf-mid"
    return "exl-conf-low"


def _status_pill(status: Any) -> str:
    if _is_empty_val(status):
        return "—"
    icons = {
        "active": "🟢",
        "excluded": "🔴",
        "included": "🔵",
        "n/a": "⚪",
        "na": "⚪",
    }
    s = str(status).strip().lower()
    icon = icons.get(s, "•")
    return f"{icon} {str(status).strip().title()}"


def _format_table_df(df: pd.DataFrame) -> pd.DataFrame:
    """Format money/pct columns and status pills for HTML table display."""
    if df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        if col == "status":
            out[col] = out[col].apply(_status_pill)
        elif col in MONEY_TABLE_COLS:
            out[col] = out[col].apply(lambda v: _fmt_money(v) if not _is_empty_val(v) else "—")
        elif col in PCT_TABLE_COLS:
            out[col] = out[col].apply(lambda v: _fmt_pct(v) if not _is_empty_val(v) else "—")
        else:
            out[col] = out[col].apply(lambda v: "—" if _is_empty_val(v) else v)
    return out


def _display_df(df: pd.DataFrame) -> pd.DataFrame:
    """Replace None/NaN with em-dash for clean table display."""
    if df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        out[col] = out[col].apply(
            lambda v: "—"
            if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip().lower() in ("none", "nan", "")
            else v
        )
    return out


def _render_data_table(df: pd.DataFrame) -> None:
    """Render formatted table as HTML with animations."""
    if df.empty:
        st.caption("No rows to display.")
        return
    display = _format_table_df(df)
    html = display.to_html(index=False, escape=True, border=0, na_rep="—")
    st.markdown(f'<div class="exl-data-table exl-animate-in">{html}</div>', unsafe_allow_html=True)


def _render_slip_tabs(rec: dict[str, Any], slip_idx: int) -> None:
    """Tabbed slip detail view with badge counts and formatted tables."""
    limits = rec.get("limits_sublimits") or []
    deductibles = rec.get("deductibles") or []
    waiting = rec.get("waiting_periods") or []
    cat = rec.get("cat_peril_summary") or []
    preview = rec.get("raw_text_preview") or ""

    tab_labels = [
        f"Limits & Sublimits ({len(limits)})",
        f"Deductibles ({len(deductibles)})",
        f"Waiting Periods ({len(waiting)})",
        f"CAT Perils ({len(cat)})",
        f"Source Text ({1 if preview else 0})",
    ]

    tabs = st.tabs(tab_labels)

    with tabs[0]:
        df_lim = pd.DataFrame(limits)
        if not df_lim.empty:
            show = [c for c in ["row_type", "peril", "region", "description", "amount", "status", "basis"] if c in df_lim.columns]
            _render_data_table(df_lim[show])
        else:
            st.warning("No limit or sublimit rows were extracted from this slip.")

    with tabs[1]:
        df_ded = pd.DataFrame(deductibles)
        if not df_ded.empty:
            show = [
                c for c in [
                    "peril", "region", "hazard_zone", "coverage_type", "deductible_type",
                    "amount", "pct", "min_amount", "max_amount", "basis",
                ]
                if c in df_ded.columns
            ]
            _render_data_table(df_ded[show])
        else:
            st.warning("No deductible rows were extracted from this slip.")

    with tabs[2]:
        df_w = pd.DataFrame(waiting)
        if not df_w.empty:
            _render_data_table(df_w)
        else:
            st.caption("No waiting periods identified.")

    with tabs[3]:
        df_cat = pd.DataFrame(cat)
        if not df_cat.empty:
            _render_data_table(
                df_cat[["peril_code", "peril_name", "primary_limit", "limit_status", "sublimit_count", "deductible_count"]]
            )
        else:
            st.caption("No CAT peril summary available.")

    with tabs[4]:
        st.text(preview[:2500] or "No source text extracted. Scanned PDFs require Tesseract OCR.")


def _clear_all() -> None:
    st.session_state.slip_upload_nonce += 1
    st.session_state.slip_completed = False
    st.session_state.slip_error = None
    st.session_state.slip_traceback = None
    st.session_state.slip_records = []
    st.session_state.slip_paths = {}
    st.session_state.slip_stats = {}
    st.rerun()


def _render_summary_metrics(rec: dict[str, Any]) -> None:
    part = rec.get("participation_pct") or rec.get("coinsurance_pct")
    score = rec.get("confidence_score", 0)
    conf_cls = _conf_class(score)
    cards = [
        ("Total Insurable Value", _fmt_money(rec.get("tiv")), ""),
        ("Program Limit", _fmt_money(rec.get("limit_of_liability")), ""),
        ("Participation", _fmt_pct(part), ""),
        ("Confidence Score", f"{score}%", conf_cls),
    ]
    cards_html = "".join(
        f'<div class="exl-metric">'
        f'<div class="exl-metric-label">{label}</div>'
        f'<div class="exl-metric-value {extra}">{val}</div>'
        f"</div>"
        for label, val, extra in cards
    )
    st.markdown(f'<div class="exl-metrics exl-animate-in-slow">{cards_html}</div>', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="exl-detail-panel">
            <div class="exl-detail-grid">
                <div class="exl-detail-item"><strong>Named Insured:</strong> {rec.get('named_insured') or '—'}</div>
                <div class="exl-detail-item"><strong>SIR / Excess:</strong> {_fmt_money(rec.get('sir'))} / {_fmt_money(rec.get('excess_of'))}</div>
                <div class="exl-detail-item"><strong>Policy Period:</strong> {rec.get('effective_date') or '—'} → {rec.get('expiration_date') or '—'}</div>
                <div class="exl-detail-item"><strong>Blanket Deductible:</strong> {_fmt_money(rec.get('blanket_deductible'))}</div>
                <div class="exl-detail-item"><strong>Min / Max Deductible:</strong> {_fmt_money(rec.get('min_deductible'))} / {_fmt_money(rec.get('max_deductible'))}</div>
                <div class="exl-detail-item"><strong>Loss History:</strong> {rec.get('loss_history') or '—'}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@contextmanager
def _section_box():
    """Section card wrapper compatible with Streamlit 1.28+ (no border= arg)."""
    with st.container():
        st.markdown('<span class="exl-section-marker"></span>', unsafe_allow_html=True)
        yield


def _get_openai_key() -> str | None:
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return None


def main() -> None:
    _init_session()
    st.set_page_config(
        page_title="SmartCAT.AI | EXL",
        layout="wide",
        initial_sidebar_state="collapsed",
        page_icon="📄",
    )
    _inject_exl_styles()
    _render_header()

    _, reset_col = st.columns([5, 1])
    with reset_col:
        if st.button("Reset", key="clear", type="secondary", use_container_width=True):
            _clear_all()

    # Step 1 — Upload
    with _section_box():
        _render_section_header(1, "Upload Insurance Slips", "PDF · Word · Scanned Images")

        nonce = st.session_state.slip_upload_nonce
        slips = st.file_uploader(
            "Drag and drop slip files here",
            type=ACCEPT_TYPES,
            accept_multiple_files=True,
            key=f"slips_{nonce}",
            label_visibility="collapsed",
            help="Supported: PDF (text or scanned), Word (.docx), PNG, JPG, TIFF",
        )

        if slips:
            file_cols = st.columns(min(len(slips), 4))
            for i, s in enumerate(slips):
                with file_cols[i % len(file_cols)]:
                    st.markdown(
                        f"""<div style="background:{EXL_GREY_BG};border:1px solid {EXL_GREY_LIGHT};border-left:3px solid {EXL_ORANGE};
                        border-radius:4px;padding:0.6rem 0.85rem;font-size:0.82rem;font-weight:600;color:{EXL_BLACK};">
                        {s.name}</div>""",
                        unsafe_allow_html=True,
                    )
        else:
            st.markdown(
                f"""<div style="text-align:center;padding:1.5rem;color:{EXL_GREY_MID};font-size:0.85rem;">
                No files selected — browse or drag files above</div>""",
                unsafe_allow_html=True,
            )

    # Step 2 — Extract
    with _section_box():
        _render_section_header(2, "Run Extraction")

        run_disabled = not slips
        run = st.button(
            "Extract Slip Data",
            type="primary",
            disabled=run_disabled,
            use_container_width=True,
        )
        if run_disabled:
            st.caption("Upload at least one slip file to enable extraction.")

    if st.session_state.slip_error:
        st.error(f"**Extraction failed:** {st.session_state.slip_error}")
        if st.session_state.slip_traceback:
            with st.expander("Technical details"):
                st.code(st.session_state.slip_traceback, language="python")

    # Step 3 — Results
    if st.session_state.slip_completed and st.session_state.slip_records:
        stats = st.session_state.slip_stats
        paths = st.session_state.slip_paths

        with _section_box():
            _render_section_header(3, "Extraction Results", f"{stats.get('elapsed_sec', 0)}s processing time")

            st.markdown(
                f"""<div class="exl-success-banner exl-animate-in">
                    <div class="exl-success-dot"></div>
                    <div class="exl-success-text">
                        <b>{stats.get('slip_count', 0)} slip(s)</b> processed successfully —
                        <b>{stats.get('total_limits', 0)}</b> limit rows &nbsp;·&nbsp;
                        <b>{stats.get('total_deductibles', 0)}</b> deductible rows extracted
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )

            dl1, dl2 = st.columns(2)
            xlsx_p = paths.get("xlsx")
            json_p = paths.get("json")
            if xlsx_p and Path(xlsx_p).exists():
                with dl1:
                    st.download_button(
                        "Download Excel Report",
                        data=Path(xlsx_p).read_bytes(),
                        file_name=Path(xlsx_p).name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="dl_xlsx",
                    )
            if json_p and Path(json_p).exists():
                with dl2:
                    st.download_button(
                        "Download JSON",
                        data=Path(json_p).read_bytes(),
                        file_name=Path(json_p).name,
                        mime="application/json",
                        use_container_width=True,
                        key="dl_json",
                    )

            for idx, rec in enumerate(st.session_state.slip_records):
                st.markdown("---")
                st.markdown(
                    f"""<div class="exl-slip-title exl-animate-in">
                        <span class="exl-slip-title-icon">📄</span>
                        {rec.get('source_file', f'Slip {idx + 1}')}
                    </div>""",
                    unsafe_allow_html=True,
                )
                _render_summary_metrics(rec)
                _render_slip_tabs(rec, idx)

    if run and slips:
        st.session_state.slip_completed = False
        st.session_state.slip_error = None
        st.session_state.slip_traceback = None

        openai_key = _get_openai_key()
        t0 = time.perf_counter()

        with st.status("Processing slips…", expanded=True) as status:
            try:
                TMP_SLIPS.mkdir(parents=True, exist_ok=True)
                OUT_SLIP.mkdir(parents=True, exist_ok=True)

                slip_paths: list[Path] = []
                for uf in slips:
                    tp = TMP_SLIPS / uf.name
                    tp.write_bytes(uf.getvalue())
                    slip_paths.append(tp)

                engine = SlipExtractionEngine(openai_key=openai_key)
                records: list[dict[str, Any]] = []
                for p in slip_paths:
                    status.write(f"Analyzing **{p.name}**…")
                    rec = engine.extract_file(p)
                    records.append(rec)
                    status.write(
                        f"**{p.name}** — TIV: {_fmt_money(rec.get('tiv'))} · "
                        f"{len(rec.get('limits_sublimits') or [])} limits · "
                        f"{len(rec.get('deductibles') or [])} deductibles"
                    )

                stem = Path(slips[0].name).stem
                if len(slips) > 1:
                    stem = "batch_slips"
                json_path = OUT_SLIP / f"{stem}_extracted.json"
                xlsx_path = OUT_SLIP / f"{stem}_extracted.xlsx"
                engine.save_outputs(records, json_path, xlsx_path)

                elapsed = round(time.perf_counter() - t0, 1)
                st.session_state.slip_records = records
                st.session_state.slip_paths = {"json": str(json_path), "xlsx": str(xlsx_path)}
                st.session_state.slip_stats = {
                    "slip_count": len(records),
                    "elapsed_sec": elapsed,
                    "total_limits": sum(len(r.get("limits_sublimits") or []) for r in records),
                    "total_deductibles": sum(len(r.get("deductibles") or []) for r in records),
                }
                st.session_state.slip_completed = True
                status.update(label="Extraction complete", state="complete")
                st.rerun()

            except Exception as e:
                log.exception("Slip extraction failed: %s", e)
                st.session_state.slip_error = f"{type(e).__name__}: {e}"
                st.session_state.slip_traceback = traceback.format_exc()
                status.update(label="Extraction failed", state="error")

    st.markdown(
        f"""<div class="exl-footer">
        &copy; 2026 <strong>EXL</strong> · SmartCAT.AI · Insurance Slip Intelligence Platform
        <div class="exl-footer-credit">Designed &amp; developed by <b>Satyam Mishra</b></div>
        </div>""",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
