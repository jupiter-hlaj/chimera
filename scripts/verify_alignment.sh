#!/bin/bash
set -e

# Get Stack Outputs
API_URL=$(aws cloudformation describe-stacks --stack-name chimera-data-ingestion-dev --query "Stacks[0].Outputs[?OutputKey=='DashboardApiUrl'].OutputValue" --output text)
PROCESSED_BUCKET=$(aws cloudformation describe-stacks --stack-name chimera-data-ingestion-dev --query "Stacks[0].Outputs[?OutputKey=='ProcessedBucketName'].OutputValue" --output text)

echo "API URL: $API_URL"
echo "Processed Bucket: $PROCESSED_BUCKET"

# Trigger Alignment
echo "Triggering Alignment..."
curl -X POST "$API_URL/process"
echo ""

# Wait
echo "Waiting 30 seconds for processing..."
sleep 30

# Check Status
echo "Checking Status..."
curl "$API_URL/processed"
echo ""

# List S3
echo "Listing S3 Bucket..."
aws s3 ls "s3://$PROCESSED_BUCKET/" --human-readable
