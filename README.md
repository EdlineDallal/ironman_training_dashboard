# Triathlon Training Dashboard — November 2026 update

Based on the existing `app.py` plus the charts in both `tracking_progress.ipynb` notebooks. The repository's original `workouts.csv` is retained for data integrity. Upload the latest TrainingPeaks ZIP export (2026-07-02 to 2026-11-14) in the Streamlit sidebar to analyze the newer data.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The dashboard reads the repository's existing `workouts.csv` by default. You can upload a later `workouts.csv` or an export ZIP in the sidebar; the upload replaces the display data for the current session, not the file on disk. To make it permanent replace the bundled `workouts.csv`.

Use the separate `wellness.csv` template for Garmin/manual daily wellness data (HRV, resting HR, sleep hours, Body Battery, optional notes). The TrainingPeaks workout export does **not** contain those fields. The app offers an editable form and CSV export; download your changes to retain them, or replace `wellness.csv` on disk.

## What is included
- All original graphs and tabs (training-plan, weekly TSS, PMC, discipline comparisons, raw workouts).
- New `Weekly Coach Review` with current-week and previous-week breakdown and automatically generated *data-grounded* observations.
- New `Load & Recovery` with CTL/ATL/TSB, 28-day CTL trend, TSS completeness indicators and wellness data.
- New `Performance & Quality` with session-level bike power/HR/IF, running pace/cadence/HR, swim pace and data-quality checks.
- Exact day-of-week weekly grouping **Sunday–Saturday** for the new tabs to match the coach's 8–14 November reporting week. Original tabs retain their own Monday–Sunday grouping.

## Limitations (important)
- The exported workout summary cannot support per-segment cardiac drift, normalized power (NP), variability index (VI), efficiency factor (EF), actual ride thirds, or the Joara climb comparisons. These require time-series FIT/TCX data and correct device calibration, HR and FTP. The app labels these as unavailable rather than fabricating them.
- FTP and body mass are not available as a reliable timeline in this export, so W/kg and FTP-specific conclusions should not be inferred automatically.
- The 13-Nov `Downhill Burner` planned/placeholder-like record may duplicate a measured same-day run; flagged for review and excluded from the **new** adjusted load estimates (not deleted). Other original charts are legacy and may double count it.
- Two Nov 13–14 bike workouts lack TSS/power/HR; CTL/ATL/TSB and weekly TSS are consequently underestimates. The export starts July 2, so earliest load estimates have an unknown pre-export baseline.
- Uploading wellness data requires a separate file; data edited via Streamlit is transient unless downloaded.
- No external services or TrainingPeaks/Garmin sync are included.