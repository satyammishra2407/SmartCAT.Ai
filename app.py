#!/usr/bin/env python3
"""
SmartCAT.AI — Slip Extraction UI (EXL).

Upload insurance slips (PDF, Word, scanned images) and extract TIV, limits,
sublimits, deductibles, participation, SIR, waiting periods, and CAT perils.
"""
from __future__ import annotations

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
            border-bottom: 1px solid {EXL_GREY_LIGHT};
        }}
        #MainMenu, footer {{ visibility: hidden; }}

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
            max-width: 1180px;
        }}

        /* ── Header (Planet EXL style) ── */
        .exl-topbar {{
            background: {EXL_WHITE};
            margin: -1rem -1rem 0 -1rem;
            padding: 0.85rem 2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid {EXL_GREY_LIGHT};
        }}
        .exl-logo {{
            display: flex;
            align-items: baseline;
            gap: 6px;
        }}
        .exl-logo-mark {{
            color: {EXL_ORANGE};
            font-weight: 800;
            font-size: 1.55rem;
            letter-spacing: -0.03em;
            line-height: 1;
        }}
        .exl-logo-text {{
            color: {EXL_GREY_MID};
            font-weight: 600;
            font-size: 1.05rem;
            letter-spacing: -0.01em;
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
            margin: 0 -1rem;
            padding: 0.55rem 2rem;
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
            border-bottom: 1px solid {EXL_GREY_LIGHT};
            margin: 0 -1rem;
            padding: 1.75rem 2rem 1.5rem;
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
            color: {EXL_ORANGE};
        }}
        .exl-hero p {{
            color: {EXL_GREY_DARK};
            font-size: 0.95rem;
            margin: 0;
            max-width: 640px;
            line-height: 1.55;
        }}

        /* ── Section cards ── */
        .exl-section {{
            background: {EXL_WHITE};
            border: 1px solid {EXL_GREY_LIGHT};
            border-radius: 8px;
            padding: 1.5rem 1.75rem;
            margin-bottom: 1rem;
        }}
        .exl-section-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin: -1.5rem -1.75rem 1.1rem;
            padding: 0.7rem 1.75rem;
            background: {EXL_GREY_SECTION};
            border-bottom: 1px solid {EXL_GREY_LIGHT};
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
        }}
        .exl-section-sub {{
            font-size: 0.8rem;
            color: {EXL_GREY_MID};
            margin-left: auto;
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
            background: {EXL_GREY_BG};
            border: 1px solid {EXL_GREY_LIGHT};
            border-left: 3px solid {EXL_ORANGE};
            border-radius: 6px;
            padding: 0.85rem 1rem;
        }}
        .exl-metric-label {{
            font-size: 0.72rem;
            font-weight: 600;
            color: {EXL_GREY_MID};
            text-transform: uppercase;
            letter-spacing: 0.07em;
            margin-bottom: 4px;
        }}
        .exl-metric-value {{
            font-size: 1.15rem;
            font-weight: 700;
            color: {EXL_BLACK};
            letter-spacing: -0.02em;
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
            padding: 1.25rem 0 0.75rem;
            font-size: 0.75rem;
            color: {EXL_GREY_MID};
            border-top: 1px solid {EXL_GREY_LIGHT};
            margin-top: 2rem;
            background: {EXL_WHITE};
            margin-left: -1rem;
            margin-right: -1rem;
            padding-left: 1rem;
            padding-right: 1rem;
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
            transition: background 0.2s, transform 0.15s !important;
            box-shadow: 0 2px 8px rgba(240,90,40,0.25) !important;
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
            background: {EXL_GREY_BG};
            border: 1px solid {EXL_GREY_LIGHT};
            border-left: 3px solid {EXL_ORANGE};
            border-radius: 6px;
            padding: 0.75rem 1rem;
        }}
        div[data-testid="stMetricLabel"] {{
            font-size: 0.72rem !important;
            font-weight: 600 !important;
            color: {EXL_GREY_MID} !important;
            text-transform: uppercase !important;
            letter-spacing: 0.06em !important;
        }}
        div[data-testid="stMetricValue"] {{
            font-size: 1.2rem !important;
            font-weight: 700 !important;
            color: {EXL_BLACK} !important;
        }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 4px;
            background: {EXL_GREY_BG};
            border-radius: 8px;
            padding: 4px;
            border: 1px solid {EXL_GREY_LIGHT};
        }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 5px !important;
            font-weight: 600 !important;
            font-size: 0.82rem !important;
            color: {EXL_GREY_DARK} !important;
            padding: 6px 14px !important;
        }}
        .stTabs [aria-selected="true"] {{
            background: {EXL_WHITE} !important;
            color: {EXL_ORANGE} !important;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08) !important;
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
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header() -> None:
    st.markdown(
        f"""
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
        """,
        unsafe_allow_html=True,
    )


def _render_section_header(step: int, title: str, subtitle: str = "") -> None:
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
    cols = st.columns(4)
    fields = [
        ("Total Insurable Value", _fmt_money(rec.get("tiv"))),
        ("Program Limit", _fmt_money(rec.get("limit_of_liability"))),
        ("Participation", f"{rec.get('participation_pct') or rec.get('coinsurance_pct') or '—'}%"),
        ("Confidence Score", f"{rec.get('confidence_score', 0)}%"),
    ]
    for col, (label, val) in zip(cols, fields):
        with col:
            st.metric(label, val)

    st.markdown(
        f"""
        <div class="exl-detail-grid">
            <div class="exl-detail-item"><strong>Named Insured:</strong> {rec.get('named_insured') or '—'}</div>
            <div class="exl-detail-item"><strong>SIR / Excess:</strong> {_fmt_money(rec.get('sir'))} / {_fmt_money(rec.get('excess_of'))}</div>
            <div class="exl-detail-item"><strong>Extraction Method:</strong> {rec.get('extraction_method', '—')}</div>
            <div class="exl-detail-item"><strong>Policy Period:</strong> {rec.get('effective_date') or '—'} → {rec.get('expiration_date') or '—'}</div>
            <div class="exl-detail-item"><strong>Blanket Deductible:</strong> {_fmt_money(rec.get('blanket_deductible'))}</div>
            <div class="exl-detail-item"><strong>Min / Max Deductible:</strong> {_fmt_money(rec.get('min_deductible'))} / {_fmt_money(rec.get('max_deductible'))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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

    _, content, _ = st.columns([0.01, 1.0, 0.01])
    with content:
        hdr_l, hdr_r = st.columns([5, 1])
        with hdr_r:
            if st.button("Reset", key="clear", type="secondary", use_container_width=True):
                _clear_all()

        # Step 1 — Upload
        st.markdown('<div class="exl-section">', unsafe_allow_html=True)
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

        st.markdown("</div>", unsafe_allow_html=True)

        # Step 2 — Extract
        st.markdown('<div class="exl-section">', unsafe_allow_html=True)
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
        st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.slip_error:
            st.error(f"**Extraction failed:** {st.session_state.slip_error}")
            if st.session_state.slip_traceback:
                with st.expander("Technical details"):
                    st.code(st.session_state.slip_traceback, language="python")

        # Step 3 — Results
        if st.session_state.slip_completed and st.session_state.slip_records:
            stats = st.session_state.slip_stats
            paths = st.session_state.slip_paths

            st.markdown('<div class="exl-section">', unsafe_allow_html=True)
            _render_section_header(3, "Extraction Results", f"{stats.get('elapsed_sec', 0)}s processing time")

            st.markdown(
                f"""<div class="exl-success-banner">
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
                    f"""<div style="font-size:0.95rem;font-weight:700;color:{EXL_BLACK};margin-bottom:0.75rem;">
                    {rec.get('source_file', f'Slip {idx + 1}')}</div>""",
                    unsafe_allow_html=True,
                )
                _render_summary_metrics(rec)

                tabs = st.tabs([
                    "Limits & Sublimits",
                    "Deductibles",
                    "Waiting Periods",
                    "CAT Perils",
                    "Source Text",
                ])

                with tabs[0]:
                    df_lim = pd.DataFrame(rec.get("limits_sublimits") or [])
                    if not df_lim.empty:
                        show = [c for c in ["row_type", "peril", "region", "description", "amount", "status", "basis"] if c in df_lim.columns]
                        st.dataframe(df_lim[show], use_container_width=True, hide_index=True)
                    else:
                        st.warning("No limit or sublimit rows were extracted from this slip.")

                with tabs[1]:
                    df_ded = pd.DataFrame(rec.get("deductibles") or [])
                    if not df_ded.empty:
                        show = [c for c in ["peril", "region", "hazard_zone", "coverage_type", "deductible_type", "amount", "pct", "min_amount", "max_amount", "basis"] if c in df_ded.columns]
                        st.dataframe(df_ded[show], use_container_width=True, hide_index=True)
                    else:
                        st.warning("No deductible rows were extracted from this slip.")

                with tabs[2]:
                    df_w = pd.DataFrame(rec.get("waiting_periods") or [])
                    if not df_w.empty:
                        st.dataframe(df_w, use_container_width=True, hide_index=True)
                    else:
                        st.caption("No waiting periods identified.")

                with tabs[3]:
                    df_cat = pd.DataFrame(rec.get("cat_peril_summary") or [])
                    if not df_cat.empty:
                        st.dataframe(
                            df_cat[["peril_code", "peril_name", "primary_limit", "limit_status", "sublimit_count", "deductible_count"]],
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.caption("No CAT peril summary available.")

                with tabs[4]:
                    preview = rec.get("raw_text_preview", "")[:2500]
                    st.text(preview or "No source text extracted. Scanned PDFs require Tesseract OCR.")

            st.markdown("</div>", unsafe_allow_html=True)

        if run and slips:
            st.session_state.slip_completed = False
            st.session_state.slip_error = None
            st.session_state.slip_traceback = None

            openai_key = os.getenv("OPENAI_API_KEY")
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
