# Architecture Decisions - Phase 1: Data Ingestion

**Date:** 2026-02-05  
**Author:** Antigravity AI Assistant  
**Status:** Approved  

---

## Table of Contents

1. [Overview](#1-overview)
2. [AWS Service Selection](#2-aws-service-selection)
3. [Lambda Function Design](#3-lambda-function-design)
4. [S3 Bucket Structure](#4-s3-bucket-structure)
5. [DynamoDB Schema](#5-dynamodb-schema)
6. [Cost Optimization](#6-cost-optimization)
7. [Trade-offs and Alternatives](#7-trade-offs-and-alternatives)

---

## 1. Overview

This document records the key architectural decisions made for the Chimera Phase 1 data ingestion infrastructure. Each decision includes the rationale, alternatives considered, and any trade-offs accepted.

---

## 2. AWS Service Selection

### 2.1 Why AWS Lambda (Serverless)?

**Decision:** Use AWS Lambda for all data ingestion functions.

**Rationale:**
- **Cost-effective for sporadic workloads**: Data ingestion runs hourly or daily, not continuously
- **Zero infrastructure management**: No EC2 instances to patch or maintain
- **Auto-scaling**: Handles variable load without manual intervention
- **Pay-per-use**: Only charged for execution time, not idle time

**Alternatives Considered:**
| Alternative | Reason Not Chosen |
|-------------|-------------------|
| EC2 instances | Overkill for periodic batch jobs; requires maintenance |
| ECS Fargate | More complex; better for long-running tasks |
| Step Functions with Fargate | Reserved for Phase 2 orchestration if needed |

**Trade-offs:**
- Lambda has 15-minute execution limit (acceptable for our API calls)
- Cold starts may add 1-2 seconds latency (not critical for batch jobs)

---

### 2.2 Why x86_64 Architecture?

**Decision:** Use x86_64 architecture for all Lambda functions.

**Rationale:**
Per `CICD_GIT_BEST_PRACTICES.MD`:
> "Use x86_64 for development. This aligns the code with the GitHub Build Server, enabling 'native' speed (90-second deployments)."

- GitHub Actions runners are x86_64 by default
- Building ARM64 on x86_64 requires Docker emulation (QEMU), adding 2-5 minutes per build
- For pure Python code, there is zero performance difference

**When to Reconsider:**
- If we add compiled dependencies (NumPy, Pandas C extensions)
- At scale when Graviton's ~20% cost savings becomes material

---

### 2.3 Why S3 + Parquet?

**Decision:** Store raw data as JSON in S3, processed data as Parquet.

**Rationale:**
- **JSON for raw**: Human-readable, easy debugging, preserves exact API response
- **Parquet for processed**: Columnar format optimized for analytics queries
- **S3 for storage**: Unlimited capacity, low cost ($0.023/GB/month), integrated with all AWS services

**Alternatives Considered:**
| Alternative | Reason Not Chosen |
|-------------|-------------------|
| DynamoDB for all data | Not optimized for time-series; expensive at scale |
| Timestream | Excellent for time-series but more expensive and less flexible |
| Redshift | Overkill for Phase 1; better for Phase 3 analytics |

---

### 2.4 Why DynamoDB for Metadata?

**Decision:** Use DynamoDB for ingestion tracking metadata only.

**Rationale:**
- **Tracking state**: Need to know which data has been ingested, when, and status
- **DynamoDB strengths**: Fast point lookups, serverless, auto-scaling
- **Provisioned mode**: 5 RCU/5 WCU fits within Free Tier (25 RCU/WCU)

**Schema Design:**
```
Table: chimera-ingestion-metadata-{env}
Partition Key: source_id (String) - e.g., "planetary_Mars", "geomagnetic_k_index"
Sort Key: timestamp (String) - ISO 8601 format
```

This allows:
- Query all ingestion records for a source: `source_id = 'planetary_Mars'`
- Query specific date: `source_id = 'planetary_Mars' AND timestamp = '2014-01-01'`

---

## 3. Lambda Function Design

### 3.1 One Function Per Data Source

**Decision:** Create separate Lambda functions for each data source.

**Rationale:**
- **Single Responsibility**: Each function does one thing well
- **Independent deployment**: Can update NASA function without touching NOAA
- **Different dependencies**: Market function needs yfinance; planetary needs requests only
- **Clearer monitoring**: CloudWatch metrics per function show where issues occur

**Functions Created:**
| Function | Data Source | External Dependency |
|----------|-------------|---------------------|
| `ingest_planetary` | NASA JPL Horizons | `requests` |
| `ingest_geomagnetic` | NOAA SWPC | `requests` |
| `ingest_schumann` | Manual upload | `pandas` |
| `ingest_gcp` | Manual upload | `pandas` |
| `ingest_market` | Yahoo Finance | `yfinance`, `pandas` |

---

### 3.2 Logging Strategy

**Decision:** All functions log at DEBUG level during development.

**Rationale:**
Per `instructions.md` Phase 5:
> "Verbose Logging: All Lambda functions MUST have logging set to DEBUG level by default during development/troubleshooting."

**Log Levels Used:**
| Level | Usage |
|-------|-------|
| INFO | Key state changes (start, complete, data stored) |
| DEBUG | Request URLs, response sizes, detailed flow |
| WARNING | Missing data, optional features unavailable |
| ERROR | Failures with full stack traces |

---

### 3.3 Error Handling Pattern

**Decision:** Continue processing all items; collect errors; return partial success.

**Rationale:**
- If one planetary body fails, we should still process others
- Return HTTP 207 (Multi-Status) when some items fail
- Log all errors with full context for debugging

**Code Pattern:**
```python
results = []
errors = []

for item in items:
    try:
        result = process(item)
        results.append(result)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        errors.append({'item': item, 'error': str(e)})

return {
    'statusCode': 200 if not errors else 207,
    'body': {'results': results, 'errors': errors}
}
```

---

## 4. S3 Bucket Structure

### 4.1 Bucket Naming

**Decision:** Use account-scoped unique bucket names.

**Pattern:** `chimera-{purpose}-{env}-{account_id}`

**Examples:**
- `chimera-raw-dev-123456789012`
- `chimera-processed-prod-123456789012`

**Rationale:**
- S3 bucket names must be globally unique
- Including account ID ensures uniqueness across AWS accounts
- Including environment allows parallel dev/staging/prod buckets

---

### 4.2 Key Structure

**Decision:** Organize by data source, then by entity, then by date.

**Structure:**
```
s3://chimera-raw-{env}-{account}/
├── planetary/
│   ├── Sun/
│   │   ├── 2014-01-01.json
│   │   └── 2014-01-02.json
│   ├── Moon/
│   │   └── ...
│   └── Mars/
│       └── ...
├── geomagnetic/
│   ├── planetary_k_index/
│   │   └── 2014-01-01.json
│   └── f107_flux/
│       └── ...
├── schumann/
│   ├── uploads/     # Manual uploads go here
│   └── processed/   # Processed files stored here
├── gcp/
│   ├── uploads/
│   └── processed/
└── market/
    ├── SPY/
    │   ├── 1d/
    │   │   └── 2014-01-01.json
    │   └── 1h/
    │       └── ...
    └── VIX/
        └── ...
```

**Rationale:**
- Easy to browse in S3 console
- Efficient prefix-based listing (e.g., list all Mars data)
- Date-based files enable easy reprocessing of specific dates

---

## 5. DynamoDB Schema

### 5.1 Primary Key Design

**Decision:** Composite key with source_id (partition) + timestamp (sort).

**Rationale:**
- **source_id as partition key**: Even distribution of data across partitions
- **timestamp as sort key**: Enables range queries within a source

**Access Patterns Supported:**
| Query | Key Condition |
|-------|---------------|
| All ingestions for a source | `source_id = 'x'` |
| Specific date for a source | `source_id = 'x' AND timestamp = 'y'` |
| Date range for a source | `source_id = 'x' AND timestamp BETWEEN 'a' AND 'b'` |

---

### 5.2 Provisioned vs On-Demand

**Decision:** Use Provisioned mode with 5 RCU / 5 WCU.

**Rationale:**
Per `AWS_SAM_CDK.MD`:
> "NOTE: Using Provisioned mode to stay in Free Tier (25 RCU/WCU free)"

- Metadata writes are infrequent (once per ingestion run)
- 5 WCU supports 5 writes/second = 18,000 writes/hour (more than enough)
- Free Tier saves ~$1/month compared to On-Demand minimum

---

## 6. Cost Optimization

### 6.1 Estimated Monthly Costs

| Service | Usage | Estimated Cost |
|---------|-------|----------------|
| Lambda | ~1000 invocations, 30s avg | $0.00 (Free Tier) |
| S3 | ~10GB raw data | $0.23/month |
| DynamoDB | 5 RCU/WCU provisioned | $0.00 (Free Tier) |
| CloudWatch | Logs + metrics | $0.00 (Free Tier) |
| **Total** | | **~$0.25/month** |

### 6.2 Cost Control Measures

1. **Provisioned DynamoDB**: Stays within Free Tier
2. **x86_64 Lambdas**: Fast builds, no Docker emulation cost
3. **S3 versioning**: Enabled but can be disabled to reduce storage
4. **No NAT Gateway**: Lambdas use public endpoints directly

---

## 7. Trade-offs and Alternatives

### 7.1 Trade-offs Accepted

| Trade-off | Accepted Limitation | Benefit |
|-----------|---------------------|---------|
| No real-time Schumann API | Manual upload workflow | Avoids fragile web scraping |
| 2-year hourly market data | Use daily for 10-year history | Simpler implementation |
| No Step Functions orchestration | Manual or cron invocation | Reduced complexity for Phase 1 |
| Single region (us-east-1) | No multi-region redundancy | Lower cost and complexity |

### 7.2 Future Improvements (Phase 2+)

1. **Step Functions**: Orchestrate hourly ingestion pipeline
2. **EventBridge**: Schedule automatic daily runs
3. **Glue Catalog**: Register data for Athena queries
4. **Real-time streaming**: MSK for live Schumann/GCP feeds (if APIs become available)

---

## Document Metadata

**Created:** 2026-02-05T16:24:00-05:00  
**Approved By:** User (LGTM on implementation_plan.md)  
**Related Documents:**
- [01_api_research.md](./01_api_research.md)
- [03_implementation_log.md](./03_implementation_log.md)
