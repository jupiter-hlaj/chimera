"""
Chimera Data Ingestion - Global Consciousness Project (GCP2) Data

This Lambda function processes GCP2 Random Number Generator (RNG) data files
that have been manually uploaded to S3 (from gcp2.net downloads).

Note: GCP2 does not provide a real-time API.
Historical data must be downloaded from https://gcp2.net/data-results/data-download

Data Sources:
- GCP2 Data Download: https://gcp2.net/data-results/data-download
- Live Data Display: https://gcp2.net/#home_page_live_data
"""

import json
import logging
import os
from datetime import datetime
from typing import Any

import boto3
import pandas as pd

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Configuration
RAW_BUCKET = os.environ.get('RAW_BUCKET', '')
METADATA_TABLE = os.environ.get('METADATA_TABLE', '')

# Expected input format for manually uploaded files
UPLOAD_PREFIX = 'gcp/uploads/'
PROCESSED_PREFIX = 'gcp/processed/'


def list_pending_files() -> list:
    """
    List GCP data files pending processing.
    
    Returns:
        list: S3 keys of files to process
    """
    logger.info(f"Scanning for pending files in s3://{RAW_BUCKET}/{UPLOAD_PREFIX}")
    
    response = s3_client.list_objects_v2(
        Bucket=RAW_BUCKET,
        Prefix=UPLOAD_PREFIX,
    )
    
    files = []
    for obj in response.get('Contents', []):
        key = obj['Key']
        if key.endswith('.csv') or key.endswith('.json') or key.endswith('.txt'):
            files.append(key)
    
    logger.info(f"Found {len(files)} pending files")
    return files


def process_gcp_file(s3_key: str) -> dict:
    """
    Process a single GCP data file.
    
    Args:
        s3_key: S3 key of the file to process
    
    Returns:
        dict: Processing results
    """
    logger.info(f"Processing file: {s3_key}")
    
    # Download file
    response = s3_client.get_object(Bucket=RAW_BUCKET, Key=s3_key)
    content = response['Body'].read()
    
    # Determine file type and parse
    if s3_key.endswith('.csv'):
        df = pd.read_csv(pd.io.common.BytesIO(content))
    elif s3_key.endswith('.json'):
        data = json.loads(content.decode('utf-8'))
        df = pd.DataFrame(data)
    elif s3_key.endswith('.txt'):
        # Attempt to parse as whitespace-delimited
        df = pd.read_csv(pd.io.common.BytesIO(content), delim_whitespace=True)
    else:
        raise ValueError(f"Unsupported file format: {s3_key}")
    
    logger.info(f"Loaded {len(df)} records from file")
    logger.debug(f"Columns: {df.columns.tolist()}")
    
    # Validate expected columns for GCP data
    # Note: Actual column names depend on GCP2 export format
    # Common expected columns: timestamp, z_score, variance, egg_id
    expected_columns = ['timestamp', 'z_score']
    missing_columns = [col for col in expected_columns if col not in df.columns]
    
    if missing_columns:
        logger.warning(f"Missing expected columns: {missing_columns}")
        logger.info(f"Available columns: {df.columns.tolist()}")
    
    # Store processed data
    filename = s3_key.split('/')[-1]
    base_name = filename.rsplit('.', 1)[0]
    processed_key = f"{PROCESSED_PREFIX}{base_name}.json"
    
    s3_client.put_object(
        Bucket=RAW_BUCKET,
        Key=processed_key,
        Body=df.to_json(orient='records', date_format='iso'),
        ContentType='application/json',
        Metadata={
            'source': 'gcp2-upload',
            'original_file': s3_key,
            'record_count': str(len(df)),
            'processing_time': datetime.utcnow().isoformat(),
        }
    )
    
    logger.info(f"Stored processed data to s3://{RAW_BUCKET}/{processed_key}")
    
    return {
        'original_key': s3_key,
        'processed_key': processed_key,
        'record_count': len(df),
        'columns': df.columns.tolist(),
    }


def record_metadata(s3_key: str, result: dict, status: str) -> None:
    """
    Record processing metadata to DynamoDB.
    
    Args:
        s3_key: Original S3 key
        result: Processing results
        status: Processing status
    """
    if not METADATA_TABLE:
        logger.warning("METADATA_TABLE not configured, skipping metadata recording")
        return
    
    table = dynamodb.Table(METADATA_TABLE)
    
    table.put_item(
        Item={
            'source_id': 'gcp2_upload',
            'timestamp': datetime.utcnow().isoformat(),
            'original_key': s3_key,
            'processed_key': result.get('processed_key', ''),
            'record_count': result.get('record_count', 0),
            'status': status,
            'ingestion_time': datetime.utcnow().isoformat(),
        }
    )
    
    logger.info(f"Recorded metadata for {s3_key}")


def lambda_handler(event: dict, context: Any) -> dict:
    """
    AWS Lambda handler for GCP2 data processing.
    
    This function processes manually uploaded GCP2 RNG data files.
    
    Event Parameters:
        s3_key: Optional specific file to process. If not provided, processes all pending files.
    
    Returns:
        dict: Execution results with status and details
    """
    logger.info("=== CHIMERA GCP PROCESSING START ===")
    logger.info(f"Event: {json.dumps(event)}")
    
    # Determine files to process
    specific_key = event.get('s3_key')
    if specific_key:
        files_to_process = [specific_key]
    else:
        files_to_process = list_pending_files()
    
    if not files_to_process:
        logger.info("No files to process")
        return {
            'statusCode': 200,
            'body': {
                'message': 'No pending files to process',
                'files_processed': 0,
            }
        }
    
    logger.info(f"Processing {len(files_to_process)} files")
    
    results = []
    errors = []
    
    for s3_key in files_to_process:
        try:
            result = process_gcp_file(s3_key)
            record_metadata(s3_key, result, 'success')
            results.append(result)
            
        except Exception as e:
            logger.error(f"Error processing {s3_key}: {str(e)}", exc_info=True)
            errors.append({
                's3_key': s3_key,
                'error': str(e),
            })
            record_metadata(s3_key, {}, 'failed')
    
    logger.info("=== CHIMERA GCP PROCESSING COMPLETE ===")
    logger.info(f"Processed: {len(results)} files, Errors: {len(errors)}")
    
    return {
        'statusCode': 200 if not errors else 207,
        'body': {
            'results': results,
            'errors': errors,
            'summary': {
                'total': len(files_to_process),
                'success': len(results),
                'failed': len(errors),
            }
        }
    }
