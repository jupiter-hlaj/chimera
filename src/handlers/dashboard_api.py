"""
Chimera Dashboard API

This Lambda function provides REST API endpoints for the Chimera dashboard:
- GET /status - Ingestion status overview
- GET /health - System health check
- GET /data/{source} - Latest data for a source
- POST /ingest/{source} - Trigger ingestion for a source
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')

# Configuration
RAW_BUCKET = os.environ.get('RAW_BUCKET', '')
METADATA_TABLE = os.environ.get('METADATA_TABLE', '')

# Data source configuration
DATA_SOURCES = {
    'planetary': {
        'name': 'Planetary Positions',
        'lambda': 'chimera-ingest-planetary',
        'icon': '🪐',
        'description': 'NASA JPL Horizons API'
    },
    'geomagnetic': {
        'name': 'Geomagnetic Data',
        'lambda': 'chimera-ingest-geomagnetic',
        'icon': '🧲',
        'description': 'NOAA Space Weather'
    },
    'schumann': {
        'name': 'Schumann Resonance',
        'lambda': 'chimera-ingest-schumann',
        'icon': '🌍',
        'description': 'HeartMath GCI'
    },
    'gcp': {
        'name': 'Global Consciousness',
        'lambda': 'chimera-ingest-gcp',
        'icon': '🧠',
        'description': 'GCP2 RNG Network'
    },
    'market': {
        'name': 'Market Data',
        'lambda': 'chimera-ingest-market',
        'icon': '📈',
        'description': 'Yahoo Finance'
    }
}


def response(status_code: int, body: Any) -> dict:
    """Create API Gateway response."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }


def get_source_status(source_prefix: str) -> dict:
    """Get the latest ingestion status for a source prefix (e.g., 'planetary' matches 'planetary_Sun', 'planetary_Moon')."""
    if not METADATA_TABLE:
        return {'status': 'unknown', 'message': 'Metadata table not configured'}
    
    table = dynamodb.Table(METADATA_TABLE)
    
    # Scan for records that begin with this source prefix
    result = table.scan(
        FilterExpression=Key('source_id').begins_with(f"{source_prefix}_")
    )
    
    items = result.get('Items', [])
    
    if items:
        # Sort by ingestion_time descending and get the most recent
        items_sorted = sorted(items, key=lambda x: x.get('ingestion_time', ''), reverse=True)
        latest = items_sorted[0]
        
        return {
            'status': latest.get('status', 'unknown'),
            'last_timestamp': latest.get('timestamp'),
            'last_ingestion': latest.get('ingestion_time'),
            's3_key': latest.get('s3_key', ''),
            'record_count': len(items)  # Count of all records for this source type
        }
    
    return {'status': 'no_data', 'message': 'No ingestion records found'}


def handle_status(event: dict) -> dict:
    """Handle GET /status - return status of all data sources."""
    logger.info("Handling /status request")
    
    sources = []
    for source_key, source_info in DATA_SOURCES.items():
        # Get status using prefix matching (e.g., 'planetary' finds 'planetary_Sun', etc.)
        status = get_source_status(source_key)
        
        sources.append({
            'id': source_key,
            'name': source_info['name'],
            'icon': source_info['icon'],
            'description': source_info['description'],
            **status
        })
    
    return response(200, {
        'timestamp': datetime.utcnow().isoformat(),
        'sources': sources,
        'environment': os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'local').split('-')[-1]
    })


def handle_health(event: dict) -> dict:
    """Handle GET /health - system health check."""
    logger.info("Handling /health request")
    
    health = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'checks': {}
    }
    
    # Check S3 bucket
    try:
        s3_client.head_bucket(Bucket=RAW_BUCKET)
        health['checks']['s3_raw_bucket'] = {'status': 'ok', 'bucket': RAW_BUCKET}
    except Exception as e:
        health['status'] = 'degraded'
        health['checks']['s3_raw_bucket'] = {'status': 'error', 'error': str(e)}
    
    # Check DynamoDB table
    try:
        table = dynamodb.Table(METADATA_TABLE)
        table.table_status
        health['checks']['dynamodb_metadata'] = {'status': 'ok', 'table': METADATA_TABLE}
    except Exception as e:
        health['status'] = 'degraded'
        health['checks']['dynamodb_metadata'] = {'status': 'error', 'error': str(e)}
    
    # Check Lambda functions exist
    try:
        funcs = lambda_client.list_functions(MaxItems=20)
        chimera_funcs = [f['FunctionName'] for f in funcs['Functions'] 
                         if f['FunctionName'].startswith('chimera-')]
        health['checks']['lambda_functions'] = {
            'status': 'ok', 
            'count': len(chimera_funcs),
            'functions': chimera_funcs
        }
    except Exception as e:
        health['status'] = 'degraded'
        health['checks']['lambda_functions'] = {'status': 'error', 'error': str(e)}
    
    status_code = 200 if health['status'] == 'healthy' else 503
    return response(status_code, health)


def handle_data(event: dict, source: str) -> dict:
    """Handle GET /data/{source} - return latest data for a source."""
    logger.info(f"Handling /data/{source} request")
    
    if source not in DATA_SOURCES:
        return response(404, {'error': f'Unknown source: {source}'})
    
    # Get latest S3 key from metadata
    status = get_source_status(source)
    
    if status.get('status') == 'no_data':
        return response(404, {'error': f'No data found for source: {source}'})
    
    s3_key = status.get('s3_key', '')
    
    if not s3_key:
        return response(404, {'error': f'No S3 key found for source: {source}'})
    
    # Fetch data from S3
    try:
        obj = s3_client.get_object(Bucket=RAW_BUCKET, Key=s3_key)
        data = json.loads(obj['Body'].read().decode('utf-8'))
        
        return response(200, {
            'source': source,
            's3_key': s3_key,
            'last_modified': obj['LastModified'],
            'data': data if len(str(data)) < 50000 else {'message': 'Data truncated', 'size': len(str(data))}
        })
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return response(500, {'error': str(e)})


def handle_ingest(event: dict, source: str) -> dict:
    """Handle POST /ingest/{source} - trigger ingestion for a source."""
    logger.info(f"Handling /ingest/{source} request")
    
    if source not in DATA_SOURCES:
        return response(404, {'error': f'Unknown source: {source}'})
    
    source_info = DATA_SOURCES[source]
    env = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'dev').split('-')[-1]
    function_name = f"{source_info['lambda']}-{env}"
    
    try:
        # Parse request body for event payload
        body = {}
        if event.get('body'):
            body = json.loads(event['body'])
        
        # Invoke the ingestion Lambda
        result = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(body)
        )
        
        return response(202, {
            'message': f'Ingestion triggered for {source}',
            'function': function_name,
            'status_code': result['StatusCode'],
            'payload': body
        })
    except lambda_client.exceptions.ResourceNotFoundException:
        return response(404, {'error': f'Lambda function not found: {function_name}'})
    except Exception as e:
        logger.error(f"Error triggering ingestion: {e}")
        return response(500, {'error': str(e)})


def lambda_handler(event: dict, context: Any) -> dict:
    """AWS Lambda handler for Dashboard API."""
    logger.info(f"Dashboard API request: {json.dumps(event)}")
    
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    path_params = event.get('pathParameters') or {}
    
    # Route request
    if path == '/status':
        return handle_status(event)
    
    elif path == '/health':
        return handle_health(event)
    
    elif path.startswith('/data/'):
        source = path_params.get('source', path.split('/')[-1])
        return handle_data(event, source)
    
    elif path.startswith('/ingest/') and http_method == 'POST':
        source = path_params.get('source', path.split('/')[-1])
        return handle_ingest(event, source)
    
    else:
        return response(404, {'error': 'Not found', 'path': path})
