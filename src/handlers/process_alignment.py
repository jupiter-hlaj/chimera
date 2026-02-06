"""
Chimera Data Processing - Temporal Alignment

This Lambda function consumes raw data from S3, aligns it to a common
hourly timestamp (UTC), and produces a unified 'Master Dataset'.

Process:
1. Load latest raw data for all sources.
2. Create a master hourly DateIndex.
3. Resample/Interpolate each source to match the master index.
4. Merge into a single wide DataFrame.
5. Save to Processed S3 Bucket.
"""

import json
import logging
import os
import io
from datetime import datetime, timedelta
from typing import Any, Dict, List

import boto3
import pandas as pd
import numpy as np

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Configuration
RAW_BUCKET = os.environ.get('RAW_BUCKET', '')
PROCESSED_BUCKET = os.environ.get('PROCESSED_BUCKET', '')
METADATA_TABLE = os.environ.get('METADATA_TABLE', '')

DATA_SOURCES = [
    'market', 'planetary', 'geomagnetic', 'schumann', 'gcp'
]

def get_latest_s3_keys() -> Dict[str, List[Dict]]:
    """
    Query DynamoDB to find the latest S3 keys for all sub-entities of each source.
    Returns a dict: {'market': [{'entity': 'SPY', 'key': '...'}, ...], ...}
    """
    if not METADATA_TABLE:
        return {}
    
    table = dynamodb.Table(METADATA_TABLE)
    source_map = {}
    
    for source in DATA_SOURCES:
        # Scan for this source prefix
        # Note: In prod, query via GSI would be better, but Scan is fine for low volume
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('source_id').begins_with(f"{source}_")
        )
        
        items = response.get('Items', [])
        latest_by_entity = {}
        
        for item in items:
            entity = item['source_id'] # e.g. planetary_Sun
            
            # Simple "latest" check
            if entity not in latest_by_entity:
                latest_by_entity[entity] = item
            else:
                if item.get('ingestion_time', '') > latest_by_entity[entity].get('ingestion_time', ''):
                    latest_by_entity[entity] = item
        
        # Extract keys
        source_keys = []
        for entity_id, item in latest_by_entity.items():
            key = item.get('s3_key') or item.get('processed_key')
            if key:
                source_keys.append({
                    'entity': entity_id, 
                    'key': key,
                    'type': source
                })
                
        source_map[source] = source_keys
        
    return source_map

def load_data_frame(source_type: str, s3_key: str) -> pd.DataFrame:
    """Load data from S3 into a standardize DataFrame with 'timestamp' index."""
    try:
        obj = s3_client.get_object(Bucket=RAW_BUCKET, Key=s3_key)
        body = obj['Body'].read()
        
        df = pd.DataFrame()
        
        # Detect format
        if s3_key.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(body))
        elif s3_key.endswith('.json'):
            data = json.loads(body)
            # Handle different JSON structures
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                # Check for wrapped formats like Horizons
                if 'data' in data and isinstance(data['data'], list):
                     df = pd.DataFrame(data['data'])
                elif 'result' in data: 
                    # Raw text response from Horizons, skipped for now or need parser
                    # For now, return empty if not tabular
                    return pd.DataFrame()
                else:
                    df = pd.DataFrame([data]) # Single object
        
        if df.empty:
            return df
            
        # Standardize Timestamp Column
        # List of potential timestamp column names
        ts_cols = ['Date', 'date', 'timestamp', 'Time', 'time', 'datetime']
        ts_col = next((c for c in ts_cols if c in df.columns), None)
        
        if ts_col:
            df['timestamp'] = pd.to_datetime(df[ts_col], utc=True, errors='coerce')
            df = df.dropna(subset=['timestamp'])
            df = df.set_index('timestamp')
            df = df.sort_index()
            # Remove duplicate indices
            df = df[~df.index.duplicated(keep='last')]
        else:
            logger.warning(f"No timestamp column found in {s3_key}")
            return pd.DataFrame()
            
        return df
        
    except Exception as e:
        logger.error(f"Error loading {s3_key}: {e}")
        return pd.DataFrame()

def process_alignment() -> Dict:
    """Main execution logic."""
    logger.info("Starting Temporal Alignment...")
    
    source_map = get_latest_s3_keys()
    
    # 1. Define Master Time Range
    # We want a 1-hour heartbeat. 
    # Look back 30 days to Present + 1 day (for forecasts if any)
    end_date = datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    start_date = end_date - timedelta(days=30)
    
    master_idx = pd.date_range(start=start_date, end=end_date, freq='1h', name='timestamp')
    master_df = pd.DataFrame(index=master_idx)
    
    stats = {'sources': 0, 'columns': 0}
    
    # 2. Process each source and merge
    for source, items in source_map.items():
        logger.info(f"Processing source: {source} ({len(items)} files)")
        
        for item in items:
            df = load_data_frame(source, item['key'])
            if df.empty:
                continue
                
            entity_name = item['entity'] # e.g. planetary_Mars
            
            # Select meaningful columns
            # For Market: Close, Volume
            # For Planetary: (This needs complex parsing of text, skipped for MVP)
            # For Schumann: Frequency, Power
            
            prefix = entity_name.replace(f"{source}_", "")
            
            # Resample strategy
            resampled = pd.DataFrame()
            
            try:
                # Select numeric columns only
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) == 0:
                    continue

                # Resample to hourly
                # Market: ffill (last known price)
                # Others: mean (average over the hour) or ffill
                
                if source == 'market':
                    # Market data is usually daily. We simply ffill for the whole day.
                    # Rationale: The "state" of the market is the last Close price until open.
                    hourly = df[numeric_cols].resample('1h').ffill().reindex(master_idx, method='ffill')
                else:
                    # Others might be higher freq (Schumann) or lower
                    hourly = df[numeric_cols].resample('1h').mean()
                    hourly = hourly.reindex(master_idx, method='nearest', limit=1) # Don't fill too far gaps
                
                # Rename columns
                hourly.columns = [f"{source}_{prefix}_{c}".lower().replace(' ', '_') for c in hourly.columns]
                
                # Merge
                master_df = master_df.join(hourly)
                stats['sources'] += 1
                stats['columns'] += len(hourly.columns)
                
            except Exception as e:
                logger.warning(f"Failed to align {entity_name}: {e}")
                continue

    # 3. Save Master Dataset
    logger.info(f"Alignment Complete. Shape: {master_df.shape}")
    
    # Save as JSON (orientation='split' preserves index) or CSV
    output_key = f"master_aligned_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    
    json_buffer = master_df.reset_index().to_json(orient='records', date_format='iso')
    
    s3_client.put_object(
        Bucket=PROCESSED_BUCKET,
        Key=output_key,
        Body=json_buffer,
        ContentType='application/json'
    )
    
    # Also save a 'latest' copy
    s3_client.put_object(
        Bucket=PROCESSED_BUCKET,
        Key='latest_aligned.json',
        Body=json_buffer,
        ContentType='application/json'
    )
    
    return {
        'status': 'success',
        'key': output_key,
        'shape': str(master_df.shape),
        'stats': stats
    }

def lambda_handler(event: Dict, context: Any) -> Dict:
    """AWS Lambda Handler"""
    try:
        result = process_alignment()
        return {
            'statusCode': 200,
            'body': result
        }
    except Exception as e:
        logger.error(f"Alignment Failed: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': {'error': str(e)}
        }
