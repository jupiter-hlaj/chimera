# Phase 2: Temporal Alignment

## 🎯 Objective

The goal of Phase 2 is to **align** the disparate raw datasets acquired in Phase 1 into a unified, reliable, frequency-matched **Master Dataset**.

### 🧩 The Problem
Data sources arrive at different frequencies:
- **Market Data**: Daily (OHLCV) or Intraday, with gaps on weekends/holidays.
- **Planetary Data**: Ephemeris data (can be minute-by-minute or hourly).
- **Geomagnetic Data**: often 3-hour Kp indices or variable solar flux.
- **Schumann/GCP**: CSVs with specific timestamp formats.

To feed an AI model (Phase 3), we need a single `DataFrame` where every row represents the same time step (e.g., **1 Hour**) and all columns are aligned.

## 🏗 Architecture

### Processing Layer
A dedicated Lambda function `ChimeraAlignmentFunction` (`process_alignment.py`) handles this logic. It is decoupled from the ingestion layer.

1.  **Reads Raw Data**: Scans `METADATA_TABLE`, identifies the latest successfully ingested file for each source (Market, Planetary, Geomagnetic, Schumann, GCP).
2.  **Loads & Standardizes**:
    - Converts all `Date`/`Time` columns to UTC `datetime` objects.
    - Sets the index to the timestamp.
3.  **Master Index Creation**:
    - Determines the common time range (max start date -> min end date).
    - Generates a **Hourly Heartbeat** index: `pd.date_range(start, end, freq='1H')`.
4.  **Resampling & Merging**:
    - **Market**: `reindex(master_index, method='ffill')` to propagate last known price (e.g., over weekends).
    - **Planetary**: `reindex` with `ffill` (planetary positions change slowly).
    - **Geomagnetic/Schumann/GCP**: `resample('1H').mean()` to aggregate high-frequency data or `ffill` for low-frequency.
5.  **Output**:
    - Saves `master_aligned_{timestamp}.json` to the `PROCESSED_BUCKET`.

### 🔄 Trigger Mechanism
- **Manual API**: `POST /process` triggers the alignment job via the Dashboard.
- **Status Check**: `GET /processed` returns the latest aligned file details.

## 📊 Data Mapping

| Source | Raw Frequency | Alignment Strategy |
|--------|---------------|--------------------|
| **Market** | Daily (Trading Days) | Forward Fill (`ffill`) to fill weekends/holidays until next trading session. |
| **Planetary** | Hourly/Daily | Forward Fill or Interpolation. |
| **Geomagnetic**| 3-Hour / Variable | Resample `mean` or `max`. |
| **Schumann** | variable CSV | Resample `mean`. |
| **GCP** | variable CSV | Resample `mean`. |

## ✅ Verification
Successful alignment results in a JSON file in S3 with a shape like `(Rows, Columns)`, where Rows = Total Hours in range.

Example Output:
```json
{
  "status": "success",
  "key": "master_aligned_20260206_120000.json",
  "shape": "(720, 45)",
  "stats": {
    "sources": 5,
    "columns": 45
  }
}
```
