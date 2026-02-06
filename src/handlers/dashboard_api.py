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
from boto3.dynamodb.conditions import Key, Attr

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
        FilterExpression=Attr('source_id').begins_with(f"{source_prefix}_")
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
            's3_key': latest.get('s3_key') or latest.get('processed_key', ''),
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


def get_all_source_keys(source_prefix: str) -> list:
    """Get the latest S3 key for EACH unique sub-entity (e.g. Sun, Moon, Mars) for a source."""
    if not METADATA_TABLE:
        return []
    
    table = dynamodb.Table(METADATA_TABLE)
    
    # Scan for all records with this prefix
    result = table.scan(
        FilterExpression=Attr('source_id').begins_with(f"{source_prefix}_")
    )
    
    items = result.get('Items', [])
    if not items:
        return []

    # Group by source_id (e.g. planetary_Sun, planetary_Mars) and pick the latest for each
    latest_by_entity = {}
    for item in items:
        entity = item['source_id']
        timestamp = item.get('ingestion_time', '')
        
        if entity not in latest_by_entity or timestamp > latest_by_entity[entity]['ingestion_time']:
            latest_by_entity[entity] = item
            
    return list(latest_by_entity.values())


def handle_data(event: dict, source: str) -> dict:
    """Handle GET /data/{source} - return latest aggregated data for a source."""
    logger.info(f"Handling /data/{source} request")
    
    if source not in DATA_SOURCES:
        return response(404, {'error': f'Unknown source: {source}'})
    
    # Get latest items for all sub-entities
    latest_items = get_all_source_keys(source)
    
    if not latest_items:
        return response(404, {'error': f'No data found for source: {source}'})
    
    aggregated_data = {}
    total_size = 0
    MAX_SIZE = 5 * 1024 * 1024  # 5MB safety limit
    
    # fetch data for each entity
    for item in latest_items:
        s3_key = item.get('s3_key') or item.get('processed_key')
        if not s3_key:
            continue
            
        try:
            entity_name = item['source_id'].replace(f"{source}_", "")
            
            obj = s3_client.get_object(Bucket=RAW_BUCKET, Key=s3_key)
            content = obj['Body'].read().decode('utf-8')
            
            # Check size before parsing/adding
            if total_size + len(content) > MAX_SIZE:
                 aggregated_data[entity_name] = {'message': 'Data truncated (payload too large)', 's3_key': s3_key}
                 continue

            data = json.loads(content)
            aggregated_data[entity_name] = data
            total_size += len(content)
            
        except Exception as e:
            logger.error(f"Error fetching {s3_key}: {e}")
            continue

    return response(200, {
        'source': source,
        'timestamp': datetime.utcnow().isoformat(),
        'entities': list(aggregated_data.keys()),
        'data': aggregated_data
    })


def handle_process(event: dict) -> dict:
    """Handle POST /process - trigger data alignment."""
    logger.info("Handling /process request")
    
    env = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'dev').split('-')[-1]
    function_name = f"chimera-alignment-{env}"
    
    try:
        result = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event',  # Async
            Payload=json.dumps({})
        )
        
        return response(202, {
            'message': 'Alignment job triggered', 
            'function': function_name
        })
    except lambda_client.exceptions.ResourceNotFoundException:
        return response(404, {'error': f'Alignment function not found: {function_name}'})
    except Exception as e:
        logger.error(f"Error executing alignment: {e}")
        return response(500, {'error': str(e)})


def handle_processed_status(event: dict) -> dict:
    """Handle GET /processed - return info about the latest processed file."""
    # List objects in processed bucket
    PROCESSED_BUCKET = os.environ.get('PROCESSED_BUCKET', '')
    if not PROCESSED_BUCKET:
        # Try to guess or fail
        return response(500, {'error': 'PROCESSED_BUCKET not defined'})
        
    try:
        resp = s3_client.list_objects_v2(Bucket=PROCESSED_BUCKET, Prefix='master_aligned_', MaxKeys=1)
        if 'Contents' not in resp:
            return response(404, {'message': 'No aligned data found'})
            
        latest = resp['Contents'][0]
        return response(200, {
            'latest_file': latest['Key'],
            'last_modified': latest['LastModified'].isoformat(),
            'size': latest['Size']
        })
    except Exception as e:
        return response(500, {'error': str(e)})


def handle_analyze(event: dict) -> dict:
    """Handle POST /analyze - trigger correlation analysis."""
    logger.info("Handling /analyze request")
    
    env = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'dev').split('-')[-1]
    function_name = f"chimera-correlation-{env}"
    
    try:
        result = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event',  # Async
            Payload=json.dumps({})
        )
        
        return response(202, {
            'message': 'Correlation analysis triggered', 
            'function': function_name
        })
    except lambda_client.exceptions.ResourceNotFoundException:
        return response(404, {'error': f'Correlation function not found: {function_name}'})
    except Exception as e:
        logger.error(f"Error executing correlation analysis: {e}")
        return response(500, {'error': str(e)})


def handle_correlations(event: dict) -> dict:
    """Handle GET /correlations - return latest correlation results."""
    PROCESSED_BUCKET = os.environ.get('PROCESSED_BUCKET', '')
    if not PROCESSED_BUCKET:
        return response(500, {'error': 'PROCESSED_BUCKET not defined'})
        
    try:
        obj = s3_client.get_object(Bucket=PROCESSED_BUCKET, Key='latest_correlations.json')
        data = json.loads(obj['Body'].read().decode('utf-8'))
        return response(200, data)
    except s3_client.exceptions.NoSuchKey:
        return response(404, {'message': 'No correlations found. Run analysis first.'})
    except Exception as e:
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

    elif path == '/process' and http_method == 'POST':
        return handle_process(event)
    
    elif path == '/processed':
        return handle_processed_status(event)
    
    elif path.startswith('/data/'):
        source = path_params.get('source', path.split('/')[-1])
        return handle_data(event, source)
    
    elif path.startswith('/ingest/') and http_method == 'POST':
        source = path_params.get('source', path.split('/')[-1])
        return handle_ingest(event, source)
    
    elif path == '/analyze' and http_method == 'POST':
        return handle_analyze(event)
    
    elif path == '/correlations':
        return handle_correlations(event)
    
    else:
        return response(404, {'error': 'Not found', 'path': path})
