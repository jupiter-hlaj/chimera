"""
Chimera Data Analysis - Correlation Engine

This Lambda function analyzes the aligned master dataset to discover
correlations between market movements and celestial/geomagnetic factors.

Process:
1. Load latest_aligned.json from S3.
2. Compute pairwise Pearson correlations.
3. Compute lag correlations (market shifted by -1h to -24h).
4. Output top correlations to S3.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import boto3
import pandas as pd
import numpy as np

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
s3_client = boto3.client('s3')

# Configuration
PROCESSED_BUCKET = os.environ.get('PROCESSED_BUCKET', '')
CORRELATION_THRESHOLD = 0.1  # Lowered threshold to see more potential connections


def load_aligned_data() -> pd.DataFrame:
    """Load the latest aligned dataset from S3."""
    try:
        obj = s3_client.get_object(
            Bucket=PROCESSED_BUCKET,
            Key='latest_aligned.json'
        )
        data = json.loads(obj['Body'].read())
        df = pd.DataFrame(data)
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp').sort_index()
        
        return df
    except Exception as e:
        logger.error(f"Failed to load aligned data: {e}")
        return pd.DataFrame()


def compute_correlations(df: pd.DataFrame) -> List[Dict]:
    """Compute pairwise Pearson correlations between all numeric columns."""
    correlations = []
    
    # Get numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    if len(numeric_cols) < 2:
        return correlations
    
    # Separate market columns from others
    market_cols = [c for c in numeric_cols if c.startswith('market_')]
    other_cols = [c for c in numeric_cols if not c.startswith('market_')]
    
    # Compute correlations: market vs. other factors
    for market_col in market_cols:
        for other_col in other_cols:
            # Drop NaN pairs
            valid = df[[market_col, other_col]].dropna()
            if len(valid) < 10:  # Need enough data points
                continue
                
            try:
                r = valid[market_col].corr(valid[other_col])
                if abs(r) >= CORRELATION_THRESHOLD:
                    correlations.append({
                        'market_factor': market_col,
                        'environmental_factor': other_col,
                        'correlation': round(r, 4),
                        'lag_hours': 0,
                        'sample_size': len(valid),
                        'type': 'instant'
                    })
            except Exception:
                continue
    
    return correlations


def compute_lag_correlations(df: pd.DataFrame, max_lag: int = 24) -> List[Dict]:
    """
    Compute lag correlations.
    
    Shift environmental factors back in time (lag) to see if they
    predict future market movements.
    """
    correlations = []
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    market_cols = [c for c in numeric_cols if c.startswith('market_')]
    other_cols = [c for c in numeric_cols if not c.startswith('market_')]
    
    # Test lags: 1h, 2h, 4h, 6h, 12h, 24h
    lags = [1, 2, 4, 6, 12, 24]
    
    for lag in lags:
        if lag > max_lag:
            continue
            
        for market_col in market_cols:
            for other_col in other_cols:
                try:
                    # Shift environmental factor BACK (so past values align with future market)
                    shifted = df[other_col].shift(lag)
                    valid = pd.concat([df[market_col], shifted], axis=1).dropna()
                    
                    if len(valid) < 10:
                        continue
                    
                    r = valid.iloc[:, 0].corr(valid.iloc[:, 1])
                    
                    if abs(r) >= CORRELATION_THRESHOLD:
                        correlations.append({
                            'market_factor': market_col,
                            'environmental_factor': other_col,
                            'correlation': round(r, 4),
                            'lag_hours': lag,
                            'sample_size': len(valid),
                            'type': 'lagged'
                        })
                except Exception:
                    continue
    
    return correlations


def analyze() -> Dict:
    """Main analysis logic."""
    logger.info("Starting Correlation Analysis...")
    
    df = load_aligned_data()
    
    if df.empty:
        return {
            'status': 'error',
            'message': 'No aligned data found. Run alignment first.'
        }
    
    logger.info(f"Loaded data shape: {df.shape}")
    
    # Compute correlations
    instant_corr = compute_correlations(df)
    lag_corr = compute_lag_correlations(df)
    
    all_correlations = instant_corr + lag_corr
    
    # Sort by absolute correlation (strongest first)
    all_correlations.sort(key=lambda x: abs(x['correlation']), reverse=True)
    
    # Limit to top 50
    top_correlations = all_correlations[:50]
    
    # Build result
    result = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'data_shape': list(df.shape),
        'columns_analyzed': df.columns.tolist(),
        'total_correlations_found': len(all_correlations),
        'threshold': CORRELATION_THRESHOLD,
        'top_correlations': top_correlations
    }
    
    # Save to S3
    output_key = f"correlations_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    
    s3_client.put_object(
        Bucket=PROCESSED_BUCKET,
        Key=output_key,
        Body=json.dumps(result, indent=2),
        ContentType='application/json'
    )
    
    # Also save as 'latest'
    s3_client.put_object(
        Bucket=PROCESSED_BUCKET,
        Key='latest_correlations.json',
        Body=json.dumps(result, indent=2),
        ContentType='application/json'
    )
    
    logger.info(f"Analysis complete. Found {len(all_correlations)} correlations above threshold.")
    
    return {
        'status': 'success',
        'key': output_key,
        'correlations_found': len(all_correlations),
        'top_correlation': top_correlations[0] if top_correlations else None
    }


def lambda_handler(event: Dict, context: Any) -> Dict:
    """AWS Lambda Handler"""
    try:
        result = analyze()
        return {
            'statusCode': 200,
            'body': result
        }
    except Exception as e:
        logger.error(f"Analysis Failed: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': {'error': str(e)}
        }
