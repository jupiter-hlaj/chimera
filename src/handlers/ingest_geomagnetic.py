"""
Chimera Data Ingestion - NOAA Geomagnetic/Solar Data

This Lambda function fetches geomagnetic and solar activity data from NOAA SWPC
and stores the raw JSON response in S3.

Data Sources:
- Planetary K-Index: https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json
- Solar Radio Flux: https://services.swpc.noaa.gov/json/f107_cm_flux.json
- Historical Archive: ftp://ftp.swpc.noaa.gov/pub/indices/old_indices/
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

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

# NOAA SWPC API endpoints
NOAA_ENDPOINTS = {
    'planetary_k_index': 'https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json',
    'planetary_k_index_1m': 'https://services.swpc.noaa.gov/json/planetary_k_index_1m.json',
    'boulder_k_index': 'https://services.swpc.noaa.gov/json/boulder_k_index_1m.json',
    'f107_flux': 'https://services.swpc.noaa.gov/json/f107_cm_flux.json',
    'solar_radio_flux': 'https://services.swpc.noaa.gov/json/solar-radio-flux.json',
    'sunspot_report': 'https://services.swpc.noaa.gov/json/sunspot_report.json',
}


def fetch_noaa_data(endpoint_name: str) -> dict:
    """
    Fetch data from a NOAA SWPC API endpoint.
    
    Args:
        endpoint_name: Name of the endpoint to fetch
    
    Returns:
        dict: API response data
    """
    url = NOAA_ENDPOINTS.get(endpoint_name)
    if not url:
        raise ValueError(f"Unknown endpoint: {endpoint_name}")
    
    logger.info(f"Fetching NOAA data from endpoint: {endpoint_name}")
    logger.debug(f"URL: {url}")
    
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    logger.info(f"Successfully fetched {len(data) if isinstance(data, list) else 'object'} records from {endpoint_name}")
    
    return data


def store_to_s3(data: Any, endpoint_name: str, date_str: str) -> str:
    """
    Store raw NOAA data to S3.
    
    Args:
        data: Raw API response data
        endpoint_name: Name of the data source endpoint
        date_str: Date string for the data
    
    Returns:
        str: S3 key where data was stored
    """
    s3_key = f"geomagnetic/{endpoint_name}/{date_str}.json"
    
    logger.info(f"Storing data to s3://{RAW_BUCKET}/{s3_key}")
    
    s3_client.put_object(
        Bucket=RAW_BUCKET,
        Key=s3_key,
        Body=json.dumps(data, indent=2),
        ContentType='application/json',
        Metadata={
            'source': 'noaa-swpc',
            'endpoint': endpoint_name,
            'ingestion_time': datetime.utcnow().isoformat(),
        }
    )
    
    logger.info(f"Successfully stored data to S3")
    return s3_key


def record_metadata(endpoint_name: str, date_str: str, s3_key: str, status: str, record_count: int = 0) -> None:
    """
    Record ingestion metadata to DynamoDB.
    
    Args:
        endpoint_name: Name of the data source endpoint
        date_str: Date string for the data
        s3_key: S3 key where data was stored
        status: Ingestion status ('success' or 'failed')
        record_count: Number of records ingested
    """
    if not METADATA_TABLE:
        logger.warning("METADATA_TABLE not configured, skipping metadata recording")
        return
    
    table = dynamodb.Table(METADATA_TABLE)
    
    table.put_item(
        Item={
            'source_id': f'geomagnetic_{endpoint_name}',
            'timestamp': date_str,
            's3_key': s3_key,
            'status': status,
            'record_count': record_count,
            'ingestion_time': datetime.utcnow().isoformat(),
        }
    )
    
    logger.info(f"Recorded metadata for {endpoint_name} on {date_str}")


def lambda_handler(event: dict, context: Any) -> dict:
    """
    AWS Lambda handler for NOAA geomagnetic data ingestion.
    
    Event Parameters:
        date: Optional target date (YYYY-MM-DD). Defaults to today.
        endpoints: Optional list of endpoints. Defaults to all endpoints.
    
    Returns:
        dict: Execution results with status and details
    """
    logger.info("=== CHIMERA GEOMAGNETIC INGESTION START ===")
    logger.info(f"Event: {json.dumps(event)}")
    
    # Parse parameters
    target_date = event.get('date')
    if not target_date:
        target_date = datetime.utcnow().strftime('%Y-%m-%d')
    
    endpoints = event.get('endpoints', list(NOAA_ENDPOINTS.keys()))
    
    logger.info(f"Processing date: {target_date}")
    logger.info(f"Processing endpoints: {endpoints}")
    
    results = []
    errors = []
    
    for endpoint_name in endpoints:
        try:
            # Fetch data from API
            data = fetch_noaa_data(endpoint_name)
            
            # Count records
            record_count = len(data) if isinstance(data, list) else 1
            
            # Store to S3
            s3_key = store_to_s3(data, endpoint_name, target_date)
            
            # Record metadata
            record_metadata(endpoint_name, target_date, s3_key, 'success', record_count)
            
            results.append({
                'endpoint': endpoint_name,
                's3_key': s3_key,
                'record_count': record_count,
                'status': 'success',
            })
            
        except Exception as e:
            logger.error(f"Error processing endpoint {endpoint_name}: {str(e)}", exc_info=True)
            errors.append({
                'endpoint': endpoint_name,
                'error': str(e),
            })
            record_metadata(endpoint_name, target_date, '', 'failed')
    
    logger.info("=== CHIMERA GEOMAGNETIC INGESTION COMPLETE ===")
    logger.info(f"Processed: {len(results)} endpoints, Errors: {len(errors)}")
    
    return {
        'statusCode': 200 if not errors else 207,
        'body': {
            'date': target_date,
            'results': results,
            'errors': errors,
            'summary': {
                'total': len(endpoints),
                'success': len(results),
                'failed': len(errors),
            }
        }
    }
