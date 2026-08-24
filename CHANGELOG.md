# Changelog

## [Unreleased] — 2026-08-24

### Added — Export & Explainability

- **PDF Export** (`packages/reports/export.py`): ReportLab-based PDF generation with PIL chart images, metrics tables, and trade logs. Returns `ExportResult` with `run_id`, `data_hash`, and `data_quality`.
- **Excel Export** (`packages/reports/export.py`): openpyxl-based multi-sheet workbook (Summary, Trades, Equity, Drawdown, Quality). Includes data quality sheet with run metadata.
- **CSV Export** (`packages/reports/export.py`): Unified CSV format for trades, equity curves, and scenario results. All exports include `data_quality` and `run_id`.
- **Feature Importance** (`packages/explainability/importance.py`): Permutation importance and SHAP-like approximation for LSTM/Transformer models. Results include `run_id`, `data_hash`, and `splits_used`.
- **Model Comparison** (`packages/explainability/comparison.py`): Walk-forward results aggregation and Diebold-Mariano statistical test. Returns `ModelComparison` with full metadata.
- **API Endpoints** (`apps/api/export_routes.py`):
  - `POST /api/v1/export/pdf`
  - `POST /api/v1/export/excel`
  - `POST /api/v1/export/csv`
  - `GET /api/v1/explainability/importance` (@experimental)
  - `GET /api/v1/explainability/compare` (@experimental)
- **Domain Entities** (`packages/domain/entities.py`): `ExportQuality`, `ExportResult`, `FeatureImportanceItem`, `ExplainabilityResult`, `ModelComparison`.
- **Shared Constants** (`packages/domain/constants.py`): Walk-forward windows (252/63/21), export paths, quality thresholds, source identifiers.
- **Tests** (`tests/unit/test_export.py`, `tests/unit/test_explainability.py`): 21 tests covering all export formats, permutation importance, SHAP approximation, Diebold-Mariano test, walk-forward tables, and model comparison.

### Configuration

- `LML_EXPORT_PDF_PATH` — PDF export directory (default: `./exports`)
- `LML_EXPORT_EXCEL_PATH` — Excel export directory (default: `./exports`)
- `LML_EXPORT_CSV_PATH` — CSV export directory (default: `./exports`)
- `LML_WF_TRAIN` — Walk-forward train window (default: `252`)
- `LML_WF_TEST` — Walk-forward test window (default: `63`)
- `LML_WF_STEP` — Walk-forward step size (default: `21`)

### Alignment

- Explainability uses same walk-forward splits as validation (Agent 1)
- Exports include `QualityReport` and data source info (Agent 2)
- All exports embed `data_quality` and `run_id` for traceability
