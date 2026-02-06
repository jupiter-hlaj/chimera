"""
Chimera Data Ingestion - Market Data (Yahoo Finance)

This Lambda function fetches market data (stocks, ETFs, indices) from Yahoo Finance
and stores the data in S3.

Data Source: yfinance library (https://github.com/ranaroussi/yfinance)

Note: 
- Hourly data is limited to ~2 years of history
- Daily data available for full 10-year range
- For historical backfill, use daily data and interpolate
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, List

import boto3
import yfinance as yf
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

# Target symbols for Chimera
# Organized by category for correlation analysis with environmental/cosmic factors
DEFAULT_SYMBOLS = [
    # === Core Market Indices ===
    'SPY',   # S&P 500 ETF - Primary market benchmark
    'QQQ',   # Nasdaq 100 ETF - Tech sector proxy
    '^VIX',  # Volatility Index - Fear/sentiment indicator
    'DIA',   # Dow Jones Industrial Average ETF
    'IWM',   # Russell 2000 ETF - Small caps
    
    # === Safe Haven Assets ===
    'GLD',   # Gold ETF - Safe-haven asset
    'SLV',   # Silver ETF - Precious metals
    'TLT',   # 20+ Year Treasury ETF - Bond market proxy
    
    # === Energy & Commodities ===
    'USO',   # Oil ETF - Energy prices
    'UNG',   # Natural Gas ETF - Energy volatility
    'XLE',   # Energy Sector ETF
    
    # === Crypto Proxy (Sentiment) ===
    'BITO',  # Bitcoin ETF - Crypto sentiment proxy
    
    # === Sector ETFs (Sensitive to different factors) ===
    'XLF',   # Financials - Rate/economic sensitive
    'XLK',   # Technology - Growth/sentiment sensitive
    'XLU',   # Utilities - Defensive/rate sensitive
    'XLP',   # Consumer Staples - Defensive
    
    # === Individual Companies (Potentially cosmic-sensitive) ===
    # Tech Giants (high retail sentiment, behavioral patterns)
    'AAPL',  # Apple - Consumer tech bellwether
    'TSLA',  # Tesla - High volatility, sentiment-driven
    'NVDA',  # Nvidia - AI/tech momentum
    
    # Aerospace (space/cosmic exposure)
    'LMT',   # Lockheed Martin - Defense/space
    'BA',    # Boeing - Aerospace
    
    # Healthcare (biological sensitivity research)
    'JNJ',   # Johnson & Johnson - Healthcare stability
    'PFE',   # Pfizer - Pharma
    
    # Financial (economic cycle sensitive)
    'JPM',   # JPMorgan - Financial bellwether
    'GS',    # Goldman Sachs - Risk appetite proxy
]


def fetch_market_data(symbols: List[str], start_date: str, end_date: str, interval: str = '1d') -> dict:
    """
    Fetch market data from Yahoo Finance.
    
    Args:
        symbols: List of ticker symbols
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        interval: Data interval ('1h', '1d', etc.)
    
    Returns:
        dict: Dictionary of symbol -> DataFrame
    """
    logger.info(f"Fetching market data for {len(symbols)} symbols")
    logger.info(f"Date range: {start_date} to {end_date}, interval: {interval}")
    
    results = {}
    
    for symbol in symbols:
        try:
            logger.debug(f"Downloading data for {symbol}")
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, interval=interval)
            
            if df.empty:
                logger.warning(f"No data returned for {symbol}")
                continue
            
            # Reset index to make date a column
            df = df.reset_index()
            
            # Rename columns to lowercase
            df.columns = [col.lower().replace(' ', '_') for col in df.columns]
            
            # Convert datetime to string for JSON serialization
            if 'date' in df.columns:
                df['date'] = df['date'].astype(str)
            if 'datetime' in df.columns:
                df['datetime'] = df['datetime'].astype(str)
            
            results[symbol] = df
            logger.info(f"Fetched {len(df)} records for {symbol}")
            
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {str(e)}")
            raise
    
    return results


def store_to_s3(data: pd.DataFrame, symbol: str, date_str: str, interval: str) -> str:
    """
    Store market data to S3.
    
    Args:
        data: DataFrame with market data
        symbol: Ticker symbol
        date_str: Date string for the data
        interval: Data interval used
    
    Returns:
        str: S3 key where data was stored
    """
    # Clean symbol for S3 key (remove special characters)
    clean_symbol = symbol.replace('^', '').replace('.', '_')
    s3_key = f"market/{clean_symbol}/{interval}/{date_str}.json"
    
    logger.info(f"Storing data to s3://{RAW_BUCKET}/{s3_key}")
    
    s3_client.put_object(
        Bucket=RAW_BUCKET,
        Key=s3_key,
        Body=data.to_json(orient='records', date_format='iso'),
        ContentType='application/json',
        Metadata={
            'source': 'yahoo-finance',
            'symbol': symbol,
            'interval': interval,
            'record_count': str(len(data)),
            'ingestion_time': datetime.utcnow().isoformat(),
        }
    )
    
    logger.info(f"Successfully stored {len(data)} records to S3")
    return s3_key


def record_metadata(symbol: str, date_str: str, s3_key: str, status: str, record_count: int = 0) -> None:
    """
    Record ingestion metadata to DynamoDB.
    
    Args:
        symbol: Ticker symbol
        date_str: Date string for the data
        s3_key: S3 key where data was stored
        status: Ingestion status
        record_count: Number of records ingested
    """
    if not METADATA_TABLE:
        logger.warning("METADATA_TABLE not configured, skipping metadata recording")
        return
    
    table = dynamodb.Table(METADATA_TABLE)
    clean_symbol = symbol.replace('^', '').replace('.', '_')
    
    table.put_item(
        Item={
            'source_id': f'market_{clean_symbol}',
            'timestamp': date_str,
            's3_key': s3_key,
            'status': status,
            'record_count': record_count,
            'ingestion_time': datetime.utcnow().isoformat(),
        }
    )
    
    logger.info(f"Recorded metadata for {symbol} on {date_str}")


def lambda_handler(event: dict, context: Any) -> dict:
    """
    AWS Lambda handler for market data ingestion.
    
    Event Parameters:
        date: Optional target date (YYYY-MM-DD). Defaults to yesterday.
        symbols: Optional list of ticker symbols. Defaults to DEFAULT_SYMBOLS.
        interval: Optional data interval ('1h' or '1d'). Defaults to '1d'.
        start_date: Optional start date for range query.
        end_date: Optional end date for range query.
    
    Returns:
        dict: Execution results with status and details
    """
    logger.info("=== CHIMERA MARKET INGESTION START ===")
    logger.info(f"Event: {json.dumps(event)}")
    
    # Parse parameters
    interval = event.get('interval', '1d')
    symbols = event.get('symbols', DEFAULT_SYMBOLS)
    
    # Determine date range
    if event.get('start_date') and event.get('end_date'):
        start_date = event['start_date']
        end_date = event['end_date']
    else:
        target_date = event.get('date')
        if target_date:
            # Single day query
            start_date = target_date
            end_date = (datetime.strptime(target_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            # Default: fetch last 30 days of data
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
            start_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Symbols: {symbols}")
    logger.info(f"Interval: {interval}")
    
    results = []
    errors = []
    
    try:
        # Fetch all data
        market_data = fetch_market_data(symbols, start_date, end_date, interval)
        
        # Store each symbol's data
        for symbol, df in market_data.items():
            try:
                s3_key = store_to_s3(df, symbol, start_date, interval)
                record_metadata(symbol, start_date, s3_key, 'success', len(df))
                
                results.append({
                    'symbol': symbol,
                    's3_key': s3_key,
                    'record_count': len(df),
                    'status': 'success',
                })
                
            except Exception as e:
                logger.error(f"Error storing {symbol}: {str(e)}", exc_info=True)
                errors.append({
                    'symbol': symbol,
                    'error': str(e),
                })
                record_metadata(symbol, start_date, '', 'failed')
        
    except Exception as e:
        logger.error(f"Error fetching market data: {str(e)}", exc_info=True)
        errors.append({
            'error': str(e),
            'stage': 'fetch',
        })
    
    logger.info("=== CHIMERA MARKET INGESTION COMPLETE ===")
    logger.info(f"Processed: {len(results)} symbols, Errors: {len(errors)}")
    
    return {
        'statusCode': 200 if not errors else 207,
        'body': {
            'start_date': start_date,
            'end_date': end_date,
            'interval': interval,
            'results': results,
            'errors': errors,
            'summary': {
                'total': len(symbols),
                'success': len(results),
                'failed': len(errors),
            }
        }
    }
