# Phase 3: Correlation Engine

## Overview

The correlation engine analyzes the temporally-aligned master dataset to discover statistical relationships between market movements and environmental factors (planetary, geomagnetic, Schumann resonance, GCP).

## Architecture

```
latest_aligned.json (S3) → ChimeraCorrelationFunction (Lambda) → latest_correlations.json (S3)
```

## Lambda Function

**Name**: `chimera-correlation-dev`  
**Handler**: `analyze_correlations.lambda_handler`  
**Trigger**: Manual via API (`POST /analyze`)

## Correlation Methods

### 1. Instant Correlation (Lag 0)
Pearson correlation between market and environmental columns at the same timestamp.

### 2. Lag Correlation
Shifts environmental factors backward (1h, 2h, 4h, 6h, 12h, 24h) to test if they predict future market movements.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analyze` | POST | Trigger correlation analysis |
| `/correlations` | GET | Fetch latest results |

## Output Format

```json
{
  "generated_at": "2026-02-06T02:37:37Z",
  "data_shape": [721, 45],
  "total_correlations_found": 168,
  "threshold": 0.3,
  "top_correlations": [
    {
      "market_factor": "market_vix_open",
      "environmental_factor": "schumann_upload_amplitude",
      "correlation": 0.5246,
      "lag_hours": 1,
      "sample_size": 15,
      "type": "lagged"
    }
  ]
}
```

## Threshold

Only correlations with |r| ≥ 0.3 are reported. This can be adjusted in the Lambda environment variable `CORRELATION_THRESHOLD`.

## Next Steps (Phase 3.1)

- **SageMaker Studio Lab**: Use PySR for symbolic regression to find mathematical formulas
- **Back-Testing**: Apply discovered rules to historical data
- **Rule Table**: Generate actionable trading signals
