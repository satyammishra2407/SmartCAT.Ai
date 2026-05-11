"""Geocode SOV rows with Google → Nominatim fallback, scoring, audit, TIV distribution."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pandas as pd
from geopy.exc import GeocoderTimedOut
from geopy.geocoders import Nominatim

from modules.module2_geocoding.audit_logger import AuditLogger
from modules.module2_geocoding.confidence_scorer import score_for_level
from modules.module2_geocoding.distribution_logic import attach_centroid_by_city, redistribute_tiv_by_postal
from modules.module2_geocoding.fallback_chain import GeocodeHit, ResolutionLevel, google_location_type_to_level, nominatim_importance_to_level
from smartcat_logging import get_logger

logger = get_logger("module2.engine")


class GeocodingEngine:
    def __init__(
        self,
        google_maps_key: str | None = None,
        audit_path: Path | None = None,
        nominatim_user_agent: str = "SmartCAT.AI/1.0 (insurance cat modeling)",
    ):
        self.google_maps_key = google_maps_key
        self.audit = AuditLogger(audit_path or Path("output/geocoded/geocode_audit.csv"))
        self._gmaps = None
        if google_maps_key:
            try:
                import googlemaps

                self._gmaps = googlemaps.Client(key=google_maps_key)
            except Exception as e:
                logger.warning("googlemaps client unavailable: %s", e)
        self._nom = Nominatim(user_agent=nominatim_user_agent, timeout=15)

    def _query_string(self, row: dict) -> str:
        parts = []
        for k in ("Street", "street", "City", "city", "State", "state", "PostalCode", "postal_code", "Country", "country"):
            if k in row and row[k] is not None and str(row[k]).strip():
                parts.append(str(row[k]).strip())
        return ", ".join(parts)

    def _try_google(self, q: str, row_id: str) -> GeocodeHit | None:
        if not self._gmaps or not q:
            return None
        try:
            results = self._gmaps.geocode(q)
            time.sleep(0.05)  # gentle rate limit
            if not results:
                self.audit.log(row_id, q, 0, "google", None, None, False, "empty")
                return None
            r0 = results[0]
            loc = r0["geometry"]["location"]
            lt = r0.get("geometry", {}).get("location_type")
            level = google_location_type_to_level(lt)
            hit = GeocodeHit(loc["lat"], loc["lng"], level, "google", r0)
            self.audit.log(row_id, q, int(level), "google", hit.lat, hit.lon, True, lt or "")
            return hit
        except Exception as e:
            self.audit.log(row_id, q, 0, "google", None, None, False, str(e)[:200])
            logger.warning("Google geocode error: %s", e)
            return None

    def _try_nominatim(self, q: str, row_id: str) -> GeocodeHit | None:
        if not q:
            return None
        try:
            loc = self._nom.geocode(q, exactly_one=True, language="en")
            time.sleep(1.1)  # Nominatim usage policy
            if loc is None:
                self.audit.log(row_id, q, 0, "nominatim", None, None, False, "empty")
                return None
            raw = loc.raw
            imp = float(raw.get("importance", 0.4))
            tokens = len(q.split(","))
            level = nominatim_importance_to_level(imp, tokens)
            hit = GeocodeHit(float(loc.latitude), float(loc.longitude), level, "nominatim", raw)
            self.audit.log(row_id, q, int(level), "nominatim", hit.lat, hit.lon, True, "")
            return hit
        except GeocoderTimedOut:
            self.audit.log(row_id, q, 0, "nominatim", None, None, False, "timeout")
            return None
        except Exception as e:
            self.audit.log(row_id, q, 0, "nominatim", None, None, False, str(e)[:200])
            return None

    def _fallback_chain(self, row: dict, row_id: str) -> dict[str, Any]:
        q_full = self._query_string(row)
        variants = [q_full]
        city = row.get("City") or row.get("city")
        state = row.get("State") or row.get("state")
        postal = row.get("PostalCode") or row.get("postal_code")
        if city and state:
            variants.append(f"{city}, {state}")
        if postal and city:
            variants.append(f"{city}, {postal}")

        last_hit: GeocodeHit | None = None
        for q in variants:
            hit = self._try_google(q, row_id)
            if hit:
                last_hit = hit
                break
            hit = self._try_nominatim(q, row_id)
            if hit:
                last_hit = hit
                break

        if last_hit:
            primary = last_hit.provider == "google"
            conf = score_for_level(last_hit.resolution, provider_primary=primary)
            return {
                "Latitude": last_hit.lat,
                "Longitude": last_hit.lon,
                "Resolution": last_hit.resolution.name,
                "Confidence Score": conf,
                "GeocodeProvider": last_hit.provider,
            }

        self.audit.log(row_id, q_full, 99, "none", None, None, False, "all_failed")
        return {
            "Latitude": None,
            "Longitude": None,
            "Resolution": "FAILED",
            "Confidence Score": 0,
            "GeocodeProvider": "",
        }

    def geocode_dataframe(self, df: pd.DataFrame, id_column: str | None = None) -> pd.DataFrame:
        out = df.copy()
        ids = out[id_column] if id_column and id_column in out.columns else pd.Series(range(len(out)), index=out.index)

        geo_rows: list[dict[str, Any]] = []
        for idx, row in out.iterrows():
            rd = row.to_dict()
            rid = str(ids.loc[idx])
            geo_rows.append(self._fallback_chain(rd, rid))

        geo_df = pd.DataFrame(geo_rows, index=out.index)
        merged = pd.concat([out, geo_df], axis=1)

        merged["geocode_failed"] = merged["Latitude"].isna()
        merged = attach_centroid_by_city(merged)
        merged = redistribute_tiv_by_postal(merged, failed_mask_col="geocode_failed")
        merged.drop(columns=["geocode_failed"], errors="ignore", inplace=True)
        return merged

    def geocode_file(self, input_path: Path, output_path: Path, chunksize: int | None = None) -> Path:
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if input_path.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(input_path)
            out = self.geocode_dataframe(df)
            out.to_csv(output_path, index=False)
            return output_path

        if chunksize:
            first = True
            for chunk in pd.read_csv(input_path, chunksize=chunksize):
                out = self.geocode_dataframe(chunk)
                out.to_csv(output_path, mode="w" if first else "a", index=False, header=first)
                first = False
            return output_path

        df = pd.read_csv(input_path)
        out = self.geocode_dataframe(df)
        out.to_csv(output_path, index=False)
        return output_path
