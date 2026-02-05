"""
Chimera Data Ingestion - NASA JPL Horizons Planetary Data

This Lambda function fetches planetary position data from the NASA JPL Horizons API
and stores the raw JSON response in S3.

Data Source: https://ssd.jpl.nasa.gov/api/horizons.api
Documentation: https://ssd-api.jpl.nasa.gov/doc/horizons.html
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import boto3
import requests

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Configuration
RAW_BUCKET = os.environ.get('RAW_BUCKET', '')
METADATA_TABLE = os.environ.get('METADATA_TABLE', '')
HORIZONS_API_URL = 'https://ssd.jpl.nasa.gov/api/horizons.api'

# Celestial bodies to track (Horizons IDs)
CELESTIAL_BODIES = {
    '10': 'Sun',
    '301': 'Moon',
    '199': 'Mercury',
    '299': 'Venus',
    '499': 'Mars',
    '599': 'Jupiter',
    '699': 'Saturn',
}


def fetch_planetary_data(body_id: str, start_date: str, end_date: str) -> dict:
    """
    Fetch planetary state vectors from NASA JPL Horizons API.
    
    Args:
        body_id: Horizons body identifier (e.g., '499' for Mars)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    
    Returns:
        dict: API response containing ephemeris data
    """
    logger.info(f"Fetching planetary data for body {body_id} ({CELESTIAL_BODIES.get(body_id, 'Unknown')})")
    logger.debug(f"Date range: {start_date} to {end_date}")
    
    params = {
        'format': 'json',
        'COMMAND': f"'{body_id}'",
        'OBJ_DATA': 'NO',
        'MAKE_EPHEM': 'YES',
        'EPHEM_TYPE': 'VECTORS',
        'CENTER': "'500@0'",  # Solar System Barycenter
        'START_TIME': f"'{start_date}'",
        'STOP_TIME': f"'{end_date}'",
        'STEP_SIZE': "'1 h'",
        'REF_PLANE': 'ECLIPTIC',
        'REF_SYSTEM': 'ICRF',
        'OUT_UNITS': 'KM-S',
    }
    
    url = f"{HORIZONS_API_URL}?{urlencode(params, safe="'")}"
    logger.debug(f"Request URL: {url}")
    
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    
    data = response.json()
    logger.info(f"Successfully fetched data for body {body_id}")
    
    return data


def store_to_s3(data: dict, body_id: str, date_str: str) -> str:
    """
    Store raw planetary data to S3.
    
    Args:
        data: Raw API response data
        body_id: Horizons body identifier
        date_str: Date string for the data
    
    Returns:
        str: S3 key where data was stored
    """
    body_name = CELESTIAL_BODIES.get(body_id, f'body_{body_id}')
    s3_key = f"planetary/{body_name}/{date_str}.json"
    
    logger.info(f"Storing data to s3://{RAW_BUCKET}/{s3_key}")
    
    s3_client.put_object(
        Bucket=RAW_BUCKET,
        Key=s3_key,
        Body=json.dumps(data, indent=2),
        ContentType='application/json',
        Metadata={
            'source': 'nasa-jpl-horizons',
            'body_id': body_id,
            'body_name': body_name,
            'ingestion_time': datetime.utcnow().isoformat(),
        }
    )
    
    logger.info(f"Successfully stored data to S3")
    return s3_key


def record_metadata(body_id: str, date_str: str, s3_key: str, status: str) -> None:
    """
    Record ingestion metadata to DynamoDB.
    
    Args:
        body_id: Horizons body identifier
        date_str: Date string for the data
        s3_key: S3 key where data was stored
        status: Ingestion status ('success' or 'failed')
    """
    if not METADATA_TABLE:
        logger.warning("METADATA_TABLE not configured, skipping metadata recording")
        return
    
    table = dynamodb.Table(METADATA_TABLE)
    body_name = CELESTIAL_BODIES.get(body_id, f'body_{body_id}')
    
    table.put_item(
        Item={
            'source_id': f'planetary_{body_name}',
            'timestamp': date_str,
            's3_key': s3_key,
            'status': status,
            'ingestion_time': datetime.utcnow().isoformat(),
        }
    )
    
    logger.info(f"Recorded metadata for {body_name} on {date_str}")


def lambda_handler(event: dict, context: Any) -> dict:
    """
    AWS Lambda handler for planetary data ingestion.
    
    Event Parameters:
        date: Optional target date (YYYY-MM-DD). Defaults to yesterday.
        body_ids: Optional list of body IDs. Defaults to all tracked bodies.
    
    Returns:
        dict: Execution results with status and details
    """
    logger.info("=== CHIMERA PLANETARY INGESTION START ===")
    logger.info(f"Event: {json.dumps(event)}")
    
    # Parse parameters
    target_date = event.get('date')
    days_back = event.get('days_back', 7)  # Default to 7 days of data
    
    if target_date:
        # Single day query
        start_date = target_date
        end_date = (datetime.strptime(target_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        # Default: fetch last N days of data
        end_date = datetime.utcnow().strftime('%Y-%m-%d')
        start_date = (datetime.utcnow() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        target_date = start_date  # Use start date for S3 key
    
    body_ids = event.get('body_ids', list(CELESTIAL_BODIES.keys()))
    
    logger.info(f"Processing date range: {start_date} to {end_date}")
    logger.info(f"Processing bodies: {body_ids}")
    
    results = []
    errors = []
    
    for body_id in body_ids:
        try:
            # Fetch data from API
            data = fetch_planetary_data(body_id, start_date, end_date)
            
            # Store to S3
            s3_key = store_to_s3(data, body_id, target_date)
            
            # Record metadata
            record_metadata(body_id, target_date, s3_key, 'success')
            
            results.append({
                'body_id': body_id,
                'body_name': CELESTIAL_BODIES.get(body_id, 'Unknown'),
                's3_key': s3_key,
                'status': 'success',
            })
            
        except Exception as e:
            logger.error(f"Error processing body {body_id}: {str(e)}", exc_info=True)
            errors.append({
                'body_id': body_id,
                'error': str(e),
            })
            record_metadata(body_id, target_date, '', 'failed')
    
    logger.info("=== CHIMERA PLANETARY INGESTION COMPLETE ===")
    logger.info(f"Processed: {len(results)} bodies, Errors: {len(errors)}")
    
    return {
        'statusCode': 200 if not errors else 207,
        'body': {
            'date': target_date,
            'results': results,
            'errors': errors,
            'summary': {
                'total': len(body_ids),
                'success': len(results),
                'failed': len(errors),
            }
        }
    }
