# API Research - Detailed Findings

**Date:** 2026-02-05  
**Author:** Antigravity AI Assistant  
**Objective:** Research all data source APIs required for Project Chimera Phase 1 data ingestion

---

## Table of Contents

1. [NASA JPL Horizons API](#1-nasa-jpl-horizons-api)
2. [NOAA Space Weather Prediction Center](#2-noaa-space-weather-prediction-center)
3. [HeartMath Global Coherence Initiative](#3-heartmath-global-coherence-initiative)
4. [Global Consciousness Project 2.0 (GCP2)](#4-global-consciousness-project-20-gcp2)
5. [Yahoo Finance (Market Data)](#5-yahoo-finance-market-data)
6. [Summary and Recommendations](#6-summary-and-recommendations)

---

## 1. NASA JPL Horizons API

### 1.1 Discovery Process

**Step 1:** Initial attempt to access `https://ssd.jpl.nasa.gov/doc/horizons.html` returned HTTP 404.

**Step 2:** Found correct API documentation URL: `https://ssd-api.jpl.nasa.gov/doc/horizons.html`

**Step 3:** Retrieved and parsed documentation chunks from the API docs page.

### 1.2 API Specification

| Property | Value |
|----------|-------|
| **Official Name** | Horizons API |
| **Version** | 1.3 (2025 June) |
| **Documentation URL** | https://ssd-api.jpl.nasa.gov/doc/horizons.html |
| **Base Endpoint** | `https://ssd.jpl.nasa.gov/api/horizons.api` |
| **HTTP Method** | GET |
| **Authentication** | None required (public API) |
| **Rate Limiting** | Not explicitly documented; "reasonable use" expected |
| **Response Format** | JSON or plain text (controlled by `format` parameter) |

### 1.3 Key Parameters

The Horizons API supports three main ephemeris types:

1. **OBSERVER** - Apparent positions as seen from a location
2. **VECTORS** - Cartesian state vectors (position and velocity) **← Recommended for Chimera**
3. **ELEMENTS** - Orbital elements

**Common Parameters (from documentation):**

| Parameter | Description | Example |
|-----------|-------------|---------|
| `format` | Output format | `json` or `text` |
| `COMMAND` | Target body identifier | `'499'` (Mars), `'10'` (Sun) |
| `EPHEM_TYPE` | Type of ephemeris | `VECTORS` |
| `CENTER` | Reference frame center | `'500@0'` (Solar System Barycenter) |
| `START_TIME` | Ephemeris start time | `'2014-01-01'` |
| `STOP_TIME` | Ephemeris stop time | `'2014-01-02'` |
| `STEP_SIZE` | Time step | `'1 h'` (1 hour) |
| `REF_PLANE` | Reference plane | `'ECLIPTIC'` |
| `REF_SYSTEM` | Reference system | `'ICRF'` |

### 1.4 Celestial Body IDs

For Project Chimera, we need to track the following bodies:

| Body | Horizons ID | Rationale |
|------|-------------|-----------|
| Sun | 10 | Central gravitational influence |
| Moon | 301 | Strongest tidal influence on Earth |
| Mercury | 199 | "Mercury Retrograde" market patterns |
| Venus | 299 | Inner planet alignment |
| Mars | 499 | Outer planet influence |
| Jupiter | 599 | Largest gravitational influence |
| Saturn | 699 | Outer planet cycles |

### 1.5 Example API Request

**Request URL:**
```
https://ssd.jpl.nasa.gov/api/horizons.api?format=json&COMMAND='499'&OBJ_DATA='NO'&MAKE_EPHEM='YES'&EPHEM_TYPE='VECTORS'&CENTER='500@0'&START_TIME='2014-01-01'&STOP_TIME='2014-01-02'&STEP_SIZE='1 h'&REF_PLANE='ECLIPTIC'
```

**Expected Response Structure (JSON):**
```json
{
  "signature": {...},
  "result": "...ephemeris data as text block..."
}
```

The vector output includes:
- X, Y, Z position (km)
- VX, VY, VZ velocity (km/s)
- Light-time (seconds)
- Range (km)
- Range-rate (km/s)

### 1.6 Historical Data Availability

The Horizons system contains ephemeris data spanning:
- **Planets**: Centuries of accurate data
- **For our purposes**: 2014-2024 data is fully available with sub-second precision

### 1.7 Implementation Notes

1. **Batch Requests**: Can request up to 90,000 data points per query
2. **URL Encoding**: Special characters must be URL-encoded (e.g., `'` → `%27`)
3. **Time Format**: Supports ISO 8601 and calendar date formats
4. **Alternative API**: File-based API available at `https://ssd-api.jpl.nasa.gov/doc/horizons_file.html` for complex batch jobs

---

## 2. NOAA Space Weather Prediction Center

### 2.1 Discovery Process

**Step 1:** Navigated to `https://www.swpc.noaa.gov/products/planetary-k-index`

**Step 2:** Found direct link to JSON data: `https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json`

**Step 3:** Discovered full JSON directory index at `https://services.swpc.noaa.gov/json/`

### 2.2 Available JSON Endpoints

**Primary Endpoint Directory:** `https://services.swpc.noaa.gov/json/`

| Endpoint | File | Description | Size |
|----------|------|-------------|------|
| **K-Index** | `planetary_k_index_1m.json` | Planetary K-index (1-min resolution) | 27KB |
| **Boulder K** | `boulder_k_index_1m.json` | Boulder, CO K-index | 84KB |
| **Solar Flux** | `f107_cm_flux.json` | F10.7 solar radio flux | 23KB |
| **Solar Radio** | `solar-radio-flux.json` | Solar radio flux observations | 56KB |
| **Sunspots** | `sunspot_report.json` | Sunspot observations | 244KB |
| **Aurora** | `ovation_aurora_latest.json` | Aurora forecast data | 897KB |

**Subdirectories with Additional Data:**
| Directory | Contents |
|-----------|----------|
| `ace/` | ACE satellite solar wind data |
| `dscovr/` | DSCOVR satellite data |
| `goes/` | GOES satellite magnetometer data |
| `geospace/` | Geospace environment data |
| `solar-cycle/` | Solar cycle predictions |

### 2.3 K-Index Specification

The **Planetary K-index (Kp)** is the primary metric for geomagnetic activity:

| Value | Description | Market Implication (per research) |
|-------|-------------|-----------------------------------|
| 0-1 | Quiet | Normal baseline |
| 2-3 | Unsettled | Normal baseline |
| 4 | Active | Minor disturbance |
| **5+** | **Storm** | Negative sentiment, selling pressure |
| 7+ | Severe Storm | Strong negative effect |
| 8-9 | Extreme | "Panic" conditions |

**Data Update Frequency:** Every 3 hours (8 measurements per day)

### 2.4 API Response Format

**Example K-Index JSON Response:**
```json
[
  {
    "time_tag": "2026-02-05 18:00:00.000",
    "kp_index": 2.0,
    "text": "2"
  },
  ...
]
```

### 2.5 Historical Data Access

**Rolling 30-Day Text File:**
```
https://services.swpc.noaa.gov/text/daily-geomagnetic-indices.txt
```

**Archive (1994-Present):**
```
ftp://ftp.swpc.noaa.gov/pub/indices/old_indices/
```

Files in archive:
- `Kp_ap_since_1932.txt` - Complete K-index history since 1932
- Annual/monthly files for various indices

### 2.6 Implementation Notes

1. **Free Access**: No authentication or API key required
2. **Update Frequency**: Real-time data updates every 1-5 minutes
3. **Historical Depth**: Archive goes back to 1932
4. **Recommended Approach**: Pull from JSON for recent data; use FTP archive for historical backfill

---

## 3. HeartMath Global Coherence Initiative

### 3.1 Discovery Process

**Step 1:** Navigated to `https://www.heartmath.org/research/global-coherence/gcms-live-data/`

**Step 2:** Found live data page with three main data streams

**Step 3:** Web search confirmed no public JSON API; data available via website visualization

### 3.2 Data Sources Identified

**From HeartMath GCI Live Data Page:**

| Data Stream | Description | Source Link |
|-------------|-------------|-------------|
| **GCMS Magnetometer** | Schumann Resonance power (0.32-36 Hz) | https://www.heartmath.org/gci/gcms/live-data/gcms-magnetometer/ |
| **GCP 2.0 Integration** | Random Network Variance | https://gcp2.net/#home_page_live_data |
| **NOAA ACE/GOES** | Solar wind speed + magnetometer | https://www.heartmath.org/gci/gcms/live-data/noaa-ace-solar-wind-speed/ |

### 3.3 Schumann Resonance Data Specification

**What is measured:**
- Power sum across frequencies 0.32 to 36 Hz
- Captures Schumann Resonance fundamental (~7.83 Hz) and harmonics
- Calculated hourly with 24-hour moving average

**Monitoring Stations:**
| Location | Country |
|----------|---------|
| Boulder Creek | California, USA |
| Hofuf | Saudi Arabia |
| Alberta | Canada |
| Northland | New Zealand |
| Magaliesburg | South Africa |
| Pauliuku | Lithuania |

### 3.4 Data Access Challenges

**No Public API Available:**
- HeartMath displays data via JavaScript-rendered visualizations
- No documented REST API endpoint for programmatic access
- "HeartCloud API" exists but is for personal coherence devices (emWave, Inner Balance)

**Alternative Data Sources:**

1. **Zenodo Dataset:** Academic datasets may be available at https://zenodo.org/ (search "Schumann Resonance")
   
2. **Web Scraping:** Could scrape the Spectrogram Calendar but:
   - High maintenance burden
   - May violate ToS
   - Data format would need reverse-engineering

3. **Academic Research Request:** Contact HeartMath Institute directly for research data access

4. **Sierra Nevada Station (Zenodo):** Reference in project docs mentions Sierra Nevada station data on Zenodo

### 3.5 Implementation Recommendation

**For Phase 1 (Historical Backfill):**
- Download available Zenodo datasets manually
- Upload to S3 raw bucket as CSV/JSON
- Process with Lambda function

**For Phase 2+ (Live Data):**
- Evaluate web scraping feasibility
- Contact HeartMath for API access
- Consider alternative Schumann data sources (e.g., USGS)

---

## 4. Global Consciousness Project 2.0 (GCP2)

### 4.1 Discovery Process

**Step 1:** Attempted `https://noosphere.princeton.edu/data.html` - returned HTTP 404

**Step 2:** Web search found GCP2 has migrated to: `https://gcp2.net/`

**Step 3:** Discovered data download page at `https://gcp2.net/data-results/data-download`

### 4.2 Project Overview

The **Global Consciousness Project** operates a worldwide network of hardware Random Number Generators (RNGs), called "eggs." The hypothesis is that human collective consciousness can create non-random patterns in the RNG outputs during major world events.

**Key Metrics:**
| Metric | Description |
|--------|-------------|
| **Stouffer Z-score** | Measures deviation from expected randomness |
| **Max[Z]** | Maximum Z-score across network |
| **Network Variance** | Collective deviation from expected random output |

### 4.3 Data Access

**Download Page:** `https://gcp2.net/data-results/data-download`

**Note from Reddit (2026-01-26):** "GCP2 RNG data is available for download at the data-results page"

**Data Format:** Likely CSV or similar tabular format (exact format to be confirmed via download)

### 4.4 Research Correlation

Per project documentation (Holmberg, 2024):
- GCP Max[Z] correlates with VIX changes
- Explains approximately 1% of VIX variance
- Serves as leading indicator for "Black Swan" events

**Chimera Op-Code Mapping:**
| Condition | Op-Code | Action |
|-----------|---------|--------|
| Z-score > 3σ | 0x03 (GCP_CRASH) | Pre-sentiment of market disruption |

### 4.5 Implementation Recommendation

**For Phase 1:**
1. Navigate to `https://gcp2.net/data-results/data-download`
2. Download available historical data (format TBD)
3. Upload to S3 raw bucket
4. Create parser Lambda for specific file format

**For Phase 2+:**
- Investigate if real-time API exists
- Contact GCP2 maintainers for research access

---

## 5. Yahoo Finance (Market Data)

### 5.1 Discovery Process

**Step 1:** Confirmed yfinance Python library is standard approach

**Step 2:** Verified library capabilities for hourly data

### 5.2 Library Specification

| Property | Value |
|----------|-------|
| **Package Name** | `yfinance` |
| **Installation** | `pip install yfinance` |
| **GitHub** | https://github.com/ranaroussi/yfinance |
| **License** | Apache 2.0 |
| **Authentication** | None required |

### 5.3 Data Capabilities

**Supported Intervals:**
- 1m, 2m, 5m, 15m, 30m, 60m (intraday - limited history)
- 1d, 5d, 1wk, 1mo, 3mo (daily+ - full history)

**Important Limitation:** Hourly (60m) data only available for ~730 days (~2 years)

**For 10-year historical data:** Must use daily data and interpolate, OR use alternative provider

### 5.4 Example Usage

```python
import yfinance as yf

# Download SPY data
spy = yf.download("SPY", start="2014-01-01", end="2024-12-31", interval="1d")

# Returns DataFrame with:
# - Open, High, Low, Close, Adj Close, Volume
# - DateTimeIndex

# For recent hourly data:
spy_hourly = yf.download("SPY", period="60d", interval="1h")
```

### 5.5 Target Symbols

| Symbol | Description | Rationale |
|--------|-------------|-----------|
| SPY | S&P 500 ETF | Primary market benchmark |
| QQQ | Nasdaq 100 ETF | Tech sector proxy |
| ^VIX | Volatility Index | Fear/sentiment indicator |
| GLD | Gold ETF | Safe-haven asset |
| TLT | 20+ Year Treasury ETF | Bond market proxy |

### 5.6 Implementation Notes

1. **Rate Limiting:** Yahoo may throttle heavy requests; implement exponential backoff
2. **Data Quality:** Occasionally has gaps; implement validation checks
3. **Timezone:** Returns data in exchange timezone (EST/EDT for US markets)
4. **Lambda Consideration:** `yfinance` has dependencies (pandas, numpy) - will increase Lambda package size

### 5.7 Alternative Providers

If yfinance proves insufficient:
| Provider | Free Tier | Notes |
|----------|-----------|-------|
| Alpha Vantage | 5 calls/min, 500/day | Requires API key |
| Polygon.io | Limited free tier | Professional-grade |
| IEX Cloud | 50k messages/month | Good for real-time |

---

## 6. Summary and Recommendations

### 6.1 API Status Matrix

| Data Source | API Available | Auth Required | Historical Data | Real-time | Effort |
|-------------|---------------|---------------|-----------------|-----------|--------|
| NASA JPL Horizons | ✅ Yes | ❌ No | ✅ Full | ❌ No | Low |
| NOAA SWPC | ✅ Yes | ❌ No | ✅ Archive | ✅ Yes | Low |
| HeartMath/Schumann | ❌ No | N/A | ⚠️ Zenodo | ❌ No | High |
| GCP2 | ⚠️ Download | ❌ No | ✅ Download | ❌ No | Medium |
| Yahoo Finance | ✅ Library | ❌ No | ⚠️ Limited | ✅ Yes | Low |

### 6.2 Implementation Priority

**Priority 1 (Easy - Direct API):**
1. NASA JPL Horizons - Full programmatic access
2. NOAA SWPC - Full programmatic access
3. Yahoo Finance - Library-based access

**Priority 2 (Medium - Manual Download):**
4. GCP2 - Download and upload workflow
5. HeartMath/Schumann - Zenodo dataset retrieval

### 6.3 Outstanding Questions for User

1. **Schumann Data Source:** Should we pursue Zenodo datasets, web scraping, or contact HeartMath directly?

2. **Historical Market Data:** Since yfinance hourly data is limited to ~2 years, should we:
   - Use daily data for 10-year history?
   - Use alternative provider (Alpha Vantage)?
   - Accept 2-year hourly + daily for older data?

3. **Date Range Confirmation:** Project docs mention 2014-2024. Should we proceed with this range?

---

## Document Metadata

**Created:** 2026-02-05T16:21:00-05:00  
**Last Updated:** 2026-02-05T16:21:00-05:00  
**Research Duration:** ~5 minutes  
**URLs Accessed:**
- https://ssd-api.jpl.nasa.gov/doc/horizons.html
- https://www.swpc.noaa.gov/products/planetary-k-index
- https://services.swpc.noaa.gov/json/
- https://www.heartmath.org/research/global-coherence/gcms-live-data/
- https://gcp2.net/data-results/data-download (via search)
