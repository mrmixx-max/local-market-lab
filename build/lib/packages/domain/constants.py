"""Shared domain constants for Local Market Lab.

Central configuration for validation windows, export paths, and quality
thresholds. All modules import from here to ensure consistency.
"""
from __future__ import annotations

import os

# ---------- validation windows (Agent 1 alignment) ----------
WALK_FORWARD_TRAIN_WINDOW = int(os.environ.get("LML_WF_TRAIN_WINDOW", "252"))
WALK_FORWARD_TEST_WINDOW = int(os.environ.get("LML_WF_TEST_WINDOW", "63"))
WALK_FORWARD_STEP = int(os.environ.get("LML_WF_STEP", "21"))

# ---------- export paths (Agent 2 alignment) ----------
EXPORT_PDF_PATH = os.environ.get("LML_EXPORT_PDF_PATH", "./exports")
EXPORT_EXCEL_PATH = os.environ.get("LML_EXPORT_EXCEL_PATH", "./exports")
EXPORT_CSV_PATH = os.environ.get("LML_EXPORT_CSV_PATH", "./exports")

# ---------- data quality ----------
QUALITY_MIN_OBSERVATIONS = int(os.environ.get("LML_QUALITY_MIN_OBS", "30"))
QUALITY_MAX_MISSING_PCT = float(os.environ.get("LML_QUALITY_MAX_MISSING", "0.05"))

# ---------- source identifiers ----------
SOURCE_YAHOO = "yahoo"
SOURCE_ALPHAVANTAGE = "alphavantage"
SOURCE_SYNTHETIC = "synthetic"
