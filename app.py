#!/usr/bin/env python3
"""
SmartCAT.AI — Streamlit UI (single-page SOV + slips → RMS/AIR imports).
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

from modules.module1_address_scrubbing import AddressScrubbingEngine
from modules.module2_geocoding import GeocodingEngine
from modules.module3_slip_extraction import SlipExtractionEngine
from modules.module4_mapping import MappingEngine
from modules.module5_model_builder import ModelBuilderEngine
from smartcat_logging import setup_logging
from smartcat_paths import OUTPUT_DIR, PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")

setup_logging()
log = logging.getLogger("smartcat.app")

OUT_CLEAN = OUTPUT_DIR / "cleaned_sovs"
OUT_GEO = OUTPUT_DIR / "geocoded"
OUT_SLIP = OUTPUT_DIR / "extracted_slips"
OUT_MAP = OUTPUT_DIR / "mapped_codes"
OUT_IMP = OUTPUT_DIR / "model_imports"
TMP_SLIPS = PROJECT_ROOT / "output" / "_tmp_slips"


def _init_session() -> None:
    defaults = {
        "smartcat_upload_nonce": 0,
        "smartcat_completed": False,
        "smartcat_error": None,
        "smartcat_traceback": None,
        "smartcat_paths": {},
        "smartcat_stats": {},
        "smartcat_stem": "",
        "smartcat_theme": "dark",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _inject_global_styles() -> None:
    """Hide sidebar; animated background, hero, cards, buttons (keys from .env only)."""
    dark = st.session_state.smartcat_theme == "dark"
    bg = "#0a0e14" if dark else "#f0f4f8"
    fg = "#e8eef7" if dark else "#0f172a"
    card_bg = "linear-gradient(145deg, #121826 0%, #0d1118 100%)" if dark else "linear-gradient(145deg, #ffffff 0%, #f8fafc 100%)"
    card_border = "1px solid #2a3344" if dark else "1px solid #e2e8f0"

    st.markdown(
        f"""
        <style>
        /* Hide sidebar completely (no API / settings panel) */
        section[data-testid="stSidebar"] {{ display: none !important; }}
        div[data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}
        .stMainBlockContainer {{ padding-top: 1.25rem; max-width: 1100px; margin: 0 auto; }}

        .stApp {{
            background: {bg};
            color: {fg};
        }}
        .stApp::before {{
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 0;
            background:
                radial-gradient(ellipse 80% 50% at 20% -10%, {"rgba(56, 189, 248, 0.18)" if dark else "rgba(14, 165, 233, 0.12)"}, transparent 55%),
                radial-gradient(ellipse 60% 40% at 100% 0%, {"rgba(167, 139, 250, 0.14)" if dark else "rgba(139, 92, 246, 0.1)"}, transparent 50%),
                radial-gradient(ellipse 50% 30% at 50% 100%, {"rgba(34, 197, 94, 0.08)" if dark else "rgba(34, 197, 94, 0.06)"}, transparent 45%);
            animation: smartcat-bg-drift 18s ease-in-out infinite alternate;
        }}
        @keyframes smartcat-bg-drift {{
            0% {{ opacity: 0.85; filter: hue-rotate(0deg); }}
            100% {{ opacity: 1; filter: hue-rotate(12deg); }}
        }}
        .block-container {{ position: relative; z-index: 1; }}

        /* Hero */
        .smartcat-hero {{
            text-align: center;
            padding: 0.5rem 0 1.25rem;
            animation: smartcat-hero-in 0.85s cubic-bezier(0.22, 1, 0.36, 1) forwards;
        }}
        @keyframes smartcat-hero-in {{
            from {{ opacity: 0; transform: translateY(22px) scale(0.98); }}
            to {{ opacity: 1; transform: translateY(0) scale(1); }}
        }}
        .smartcat-title {{
            font-size: clamp(2rem, 5vw, 2.75rem);
            font-weight: 800;
            letter-spacing: -0.03em;
            margin: 0;
            line-height: 1.15;
        }}
        .smartcat-title .grad {{
            background: linear-gradient(105deg, #38bdf8 0%, #818cf8 35%, #34d399 70%, #22d3ee 100%);
            background-size: 200% auto;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            animation: smartcat-shimmer 4s linear infinite;
        }}
        @keyframes smartcat-shimmer {{
            0% {{ background-position: 0% center; }}
            100% {{ background-position: 200% center; }}
        }}
        .smartcat-sub {{
            margin-top: 0.65rem;
            font-size: 1.02rem;
            opacity: 0.82;
            max-width: 36rem;
            margin-left: auto;
            margin-right: auto;
            animation: smartcat-fade 1s ease 0.2s both;
        }}
        @keyframes smartcat-fade {{
            from {{ opacity: 0; }}
            to {{ opacity: 0.82; }}
        }}

        /* Upload zones pulse */
        [data-testid="stFileUploader"] {{
            border-radius: 14px;
            transition: box-shadow 0.35s ease, transform 0.35s ease;
            animation: smartcat-upload-glow 3.2s ease-in-out infinite;
        }}
        @keyframes smartcat-upload-glow {{
            0%, 100% {{ box-shadow: 0 0 0 0 rgba(56, 189, 248, 0); }}
            50% {{ box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.22), 0 8px 32px rgba(15, 23, 42, 0.12); }}
        }}
        [data-testid="stFileUploader"]:hover {{
            transform: translateY(-2px);
        }}

        /* Primary run button */
        div[data-testid="stButton"] > button[kind="primary"] {{
            border-radius: 12px !important;
            font-weight: 700 !important;
            letter-spacing: 0.02em;
            transition: transform 0.22s ease, box-shadow 0.28s ease !important;
            background: linear-gradient(135deg, #059669 0%, #10b981 45%, #34d399 100%) !important;
            border: none !important;
            box-shadow: 0 6px 24px rgba(16, 185, 129, 0.35) !important;
        }}
        div[data-testid="stButton"] > button[kind="primary"]:hover:not(:disabled) {{
            transform: translateY(-3px) scale(1.01) !important;
            box-shadow: 0 12px 36px rgba(16, 185, 129, 0.45) !important;
        }}
        div[data-testid="stButton"] > button[kind="primary"]:active:not(:disabled) {{
            transform: translateY(0) scale(0.99) !important;
        }}

        /* Section headers */
        h3 {{ animation: smartcat-slide 0.6s ease both; }}
        @keyframes smartcat-slide {{
            from {{ opacity: 0; transform: translateX(-12px); }}
            to {{ opacity: 1; transform: translateX(0); }}
        }}

        /* Summary card */
        .smartcat-summary-card {{
            background: {card_bg};
            border: {card_border};
            border-radius: 16px;
            padding: 1.35rem 1.6rem;
            margin: 1rem 0;
            box-shadow: {"0 12px 40px rgba(0,0,0,0.35)" if dark else "0 8px 30px rgba(15,23,42,0.08)"};
            animation: smartcat-card-pop 0.65s cubic-bezier(0.34, 1.56, 0.64, 1) both;
        }}
        @keyframes smartcat-card-pop {{
            0% {{ opacity: 0; transform: scale(0.94) translateY(16px); }}
            100% {{ opacity: 1; transform: scale(1) translateY(0); }}
        }}

        /* Download buttons subtle lift */
        div[data-testid="stDownloadButton"] button {{
            transition: transform 0.2s ease, box-shadow 0.2s ease !important;
            border-radius: 10px !important;
        }}
        div[data-testid="stDownloadButton"] button:hover {{
            transform: translateY(-2px);
        }}

        /* Status widget polish */
        [data-testid="stStatus"] {{
            border-radius: 12px;
        }}

        /* Secondary buttons */
        div[data-testid="stButton"] > button[kind="secondary"] {{
            border-radius: 10px !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _geocode_breakdown(df: pd.DataFrame) -> dict[str, int]:
    n = len(df)
    if n == 0:
        return {"with_coords": 0, "fallback": 0, "failed": 0, "success_high": 0}
    lat_ok = df.get("Latitude")
    lon_ok = df.get("Longitude")
    if lat_ok is None or lon_ok is None:
        return {"with_coords": 0, "fallback": 0, "failed": n, "success_high": 0}
    has_geo = lat_ok.notna() & lon_ok.notna()
    conf = pd.to_numeric(df.get("Confidence Score", pd.Series([100.0] * n)), errors="coerce").fillna(100.0)
    res = df.get("Resolution", pd.Series([""] * n)).astype(str).str.upper()
    fallback = has_geo & (res.str.contains(r"DISTRIBUTED|CITY_CENTROID", regex=True, na=False) | (conf < 60.0))
    success_high = has_geo & ~fallback
    return {
        "with_coords": int(has_geo.sum()),
        "fallback": int(fallback.sum()),
        "failed": int((~has_geo).sum()),
        "success_high": int(success_high.sum()),
    }


def _clear_all() -> None:
    st.session_state.smartcat_upload_nonce += 1
    st.session_state.smartcat_completed = False
    st.session_state.smartcat_error = None
    st.session_state.smartcat_traceback = None
    st.session_state.smartcat_paths = {}
    st.session_state.smartcat_stats = {}
    st.session_state.smartcat_stem = ""
    st.rerun()


def main() -> None:
    _init_session()
    st.set_page_config(
        page_title="SmartCAT.AI",
        layout="wide",
        initial_sidebar_state="collapsed",
        page_icon="🛰️",
    )
    _inject_global_styles()

    _, center, _ = st.columns([0.04, 1.0, 0.04])
    with center:
        bar1, bar2, bar3, bar4 = st.columns([4, 1, 1, 1])
        with bar2:
            if st.button("☀️ Light", key="theme_light", use_container_width=True):
                st.session_state.smartcat_theme = "light"
                st.rerun()
        with bar3:
            if st.button("🌙 Dark", key="theme_dark", use_container_width=True):
                st.session_state.smartcat_theme = "dark"
                st.rerun()
        with bar4:
            if st.button("Clear All", key="clear_all", help="Reset uploads and results", use_container_width=True):
                _clear_all()

        st.markdown(
            """
            <div class="smartcat-hero">
                <h1 class="smartcat-title"><span class="grad">SmartCAT.AI</span></h1>
                <p class="smartcat-sub">
                    Upload your SOV and insurance slips — generate RMS RiskLink &amp; AIR Touchstone import files in one run.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        nonce = st.session_state.smartcat_upload_nonce

        with st.container():
            st.subheader("① File uploads")
            u1, u2 = st.columns(2)
            with u1:
                sov = st.file_uploader(
                    "Statement of Values (SOV)",
                    type=["csv", "xlsx", "xls"],
                    key=f"sov_{nonce}",
                    help="Excel or CSV with locations, occupancy, construction, TIV",
                )
            with u2:
                slips = st.file_uploader(
                    "Insurance slips (PDF)",
                    type=["pdf"],
                    accept_multiple_files=True,
                    key=f"slips_{nonce}",
                    help="One or more policy slips",
                )

            fc1, fc2 = st.columns(2)
            with fc1:
                if sov:
                    st.success(f"✓ SOV: `{sov.name}`")
                else:
                    st.info("Drop or browse for **SOV** (.xlsx / .csv)")
            with fc2:
                if slips:
                    for s in slips:
                        st.success(f"✓ Slip: `{s.name}`")
                else:
                    st.info("Drop or browse for **PDF slip(s)**")

        run_disabled = sov is None or not slips
        if run_disabled:
            st.warning("Upload **both** a SOV and **at least one** PDF slip to enable the run button.")

        st.subheader("② Generate imports")
        run = st.button(
            "🚀 Generate Model Import Files",
            type="primary",
            disabled=run_disabled,
            use_container_width=True,
            key="run_pipeline_btn",
        )

        if st.session_state.smartcat_error:
            st.error(f"**Processing stopped:** {st.session_state.smartcat_error}")
            tb = st.session_state.smartcat_traceback
            if tb:
                with st.expander("Technical details (traceback)"):
                    st.code(tb, language="python")

        if st.session_state.smartcat_completed and not st.session_state.smartcat_error:
            stats = st.session_state.smartcat_stats
            paths: dict[str, Any] = st.session_state.smartcat_paths
            rate = stats.get("geocode_rate_pct", 0)
            rows_n = stats.get("rows", 0)
            geo_w = stats.get("geocode", {}).get("with_coords", 0)
            slips_n = stats.get("slips", 0)

            st.divider()
            st.subheader("③ Results")
            st.markdown(
                f"""
<div class="smartcat-summary-card">
  <div style="font-size:1.12rem;font-weight:650;margin-bottom:0.65rem;">✅ Processing complete</div>
  <hr style="border:none;border-top:1px solid rgba(148,163,184,0.35);margin:0.45rem 0;" />
  <div style="font-weight:600;margin-bottom:0.45rem;">📊 Statistics</div>
  <ul style="margin:0;padding-left:1.2rem;line-height:1.65;">
    <li>Locations processed: <b>{rows_n}</b></li>
    <li>Geocoding success rate: <b>{rate}%</b> ({geo_w} / {rows_n} with coordinates)</li>
    <li>Slips processed: <b>{slips_n}</b></li>
    <li>Time taken: <b>{stats.get("elapsed_sec", 0)} sec</b></li>
  </ul>
</div>
""",
                unsafe_allow_html=True,
            )

            rms_c, air_c = st.columns(2)
            with rms_c:
                st.markdown("##### 📥 RMS (RiskLink)")
                rp = paths.get("rms_locations")
                if rp and Path(rp).exists():
                    st.download_button(
                        "Download RMS Locations (.txt)",
                        data=Path(rp).read_bytes(),
                        file_name=Path(rp).name,
                        mime="text/plain",
                        use_container_width=True,
                        key="dl_rms_loc",
                    )
                ra = paths.get("rms_accounts")
                if ra and Path(ra).exists():
                    st.download_button(
                        "Download RMS Accounts (.txt)",
                        data=Path(ra).read_bytes(),
                        file_name=Path(ra).name,
                        mime="text/plain",
                        use_container_width=True,
                        key="dl_rms_acc",
                    )
            with air_c:
                st.markdown("##### 📥 AIR (Touchstone)")
                ac = paths.get("air_csv")
                if ac and Path(ac).exists():
                    st.download_button(
                        "Download AIR Locations (.csv)",
                        data=Path(ac).read_bytes(),
                        file_name=Path(ac).name,
                        mime="text/csv",
                        use_container_width=True,
                        key="dl_air_csv",
                    )

            with st.expander("Supporting files (optional downloads)", expanded=False):
                sup_items = [
                    ("scrubbed", "Cleaned SOV (.xlsx)"),
                    ("geocoded", "Geocoded locations (.csv)"),
                    ("mapped", "Mapped codes (.xlsx)"),
                    ("slips_json", "Extracted slips (JSON)"),
                    ("slips_xlsx", "Extracted slips (Excel)"),
                ]
                cols = st.columns(2)
                for i, (pk, label) in enumerate(sup_items):
                    pth = paths.get(pk)
                    with cols[i % 2]:
                        if pth and Path(pth).exists():
                            st.download_button(
                                f"Download — {label}",
                                data=Path(pth).read_bytes(),
                                file_name=Path(pth).name,
                                use_container_width=True,
                                key=f"sup_dl_{pk}_{nonce}",
                            )

        if run and sov and slips:
            stem = Path(sov.name).stem
            slip_metas = [(s.name, s.getvalue()) for s in slips]

            st.session_state.smartcat_completed = False
            st.session_state.smartcat_error = None
            st.session_state.smartcat_traceback = None
            st.session_state.smartcat_paths = {}
            st.session_state.smartcat_stats = {}

            translate_key = os.getenv("GOOGLE_TRANSLATE_API_KEY")
            maps_key = os.getenv("GOOGLE_MAPS_API_KEY")
            openai_key = os.getenv("OPENAI_API_KEY")

            t0 = time.perf_counter()
            status_ctx = st.status("Running pipeline…", expanded=True)

            try:
                with status_ctx:
                    status_ctx.markdown("**Step 1/5:** Address scrubbing…")
                    suf = Path(sov.name).suffix.lower()
                    raw = sov.getvalue()
                    df = pd.read_csv(pd.io.common.BytesIO(raw)) if suf == ".csv" else pd.read_excel(pd.io.common.BytesIO(raw))

                    m1 = AddressScrubbingEngine(translate_api_key=translate_key)
                    df = m1.scrub_dataframe(df)
                    OUT_CLEAN.mkdir(parents=True, exist_ok=True)
                    p1 = OUT_CLEAN / f"{stem}_scrubbed.xlsx"
                    df.to_excel(p1, index=False)
                    status_ctx.write(f"Step 1/5: Address scrubbing… ✅ Done ({len(df)} rows processed)")

                    status_ctx.markdown("**Step 2/5:** Geocoding…")
                    geo = GeocodingEngine(
                        google_maps_key=maps_key,
                        audit_path=OUT_GEO / "geocode_audit.csv",
                    )
                    df = geo.geocode_dataframe(df)
                    OUT_GEO.mkdir(parents=True, exist_ok=True)
                    p2 = OUT_GEO / f"{stem}_geocoded.csv"
                    df.to_csv(p2, index=False)
                    gb = _geocode_breakdown(df)
                    status_ctx.write(
                        f"Step 2/5: Geocoding… ✅ Done ({gb['success_high']} high-confidence, "
                        f"{gb['fallback']} approximate/fallback, {gb['failed']} without coordinates)"
                    )

                    status_ctx.markdown("**Step 3/5:** Slip extraction…")
                    TMP_SLIPS.mkdir(parents=True, exist_ok=True)
                    slip_paths: list[Path] = []
                    for fname, blob in slip_metas:
                        tp = TMP_SLIPS / f"{stem}_{fname}"
                        tp.write_bytes(blob)
                        slip_paths.append(tp)
                    slip_engine = SlipExtractionEngine(openai_key=openai_key)
                    recs = slip_engine.extract_many(slip_paths)
                    OUT_SLIP.mkdir(parents=True, exist_ok=True)
                    p3j = OUT_SLIP / f"{stem}_slips.json"
                    p3x = OUT_SLIP / f"{stem}_slips.xlsx"
                    slip_engine.save_outputs(recs, p3j, p3x)
                    slip_terms: dict[str, Any] | None = recs[0] if recs else None
                    status_ctx.write(f"Step 3/5: Slip extraction… ✅ Done ({len(slip_metas)} PDFs processed)")

                    status_ctx.markdown("**Step 4/5:** Mapping codes…")
                    mapper = MappingEngine()
                    df = mapper.map_dataframe(df)
                    OUT_MAP.mkdir(parents=True, exist_ok=True)
                    p4 = OUT_MAP / f"{stem}_mapped.xlsx"
                    df.to_excel(p4, index=False)
                    status_ctx.write(f"Step 4/5: Mapping codes… ✅ Done ({len(df)} mapped)")

                    status_ctx.markdown("**Step 5/5:** Building import files…")
                    OUT_IMP.mkdir(parents=True, exist_ok=True)
                    builder = ModelBuilderEngine()
                    built = builder.build(df, slip_terms, OUT_IMP, stem=stem)

                    paths_out: dict[str, Path] = {
                        "scrubbed": p1,
                        "geocoded": p2,
                        "slips_json": p3j,
                        "slips_xlsx": p3x,
                        "mapped": p4,
                        "rms_locations": Path(built["rms_locations"]),
                        "rms_accounts": Path(built["rms_accounts"]),
                        "air_csv": Path(built["air_csv"]),
                    }
                    status_ctx.write("Step 5/5: Building import files… ✅ Done")

                elapsed = round(time.perf_counter() - t0, 1)
                st.session_state.smartcat_paths = paths_out
                st.session_state.smartcat_stats = {
                    "rows": len(df),
                    "slips": len(slip_metas),
                    "geocode": gb,
                    "geocode_rate_pct": round(100.0 * gb["with_coords"] / max(len(df), 1), 1),
                    "elapsed_sec": elapsed,
                }
                st.session_state.smartcat_completed = True
                st.session_state.smartcat_stem = stem
                log.info("Pipeline OK stem=%s rows=%s elapsed=%ss", stem, len(df), elapsed)

                if hasattr(status_ctx, "update"):
                    status_ctx.update(label="✅ All steps complete", state="complete")

                try:
                    st.balloons()
                except Exception:
                    pass
                try:
                    st.toast("Import files are ready — scroll down to download.", icon="🎉")
                except Exception:
                    pass

            except Exception as e:
                log.exception("Pipeline failed: %s", e)
                tb = traceback.format_exc()
                st.session_state.smartcat_error = f"{type(e).__name__}: {e}"
                st.session_state.smartcat_traceback = tb
                st.session_state.smartcat_completed = False
                if hasattr(status_ctx, "update"):
                    status_ctx.update(label="Pipeline failed", state="error")
                st.error(f"Pipeline failed — stopped. **{type(e).__name__}:** {e}")
                with st.expander("Technical details (traceback)"):
                    st.code(tb, language="python")


if __name__ == "__main__":
    main()
