import json
import csv
import boto3
import logging
import re
from datetime import datetime
from io import StringIO

# Set up logging — all logs go to CloudWatch automatically
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Connect to S3
s3 = boto3.client('s3')


def clean_temperature(value):
    """
    Cleans temperature values.
    Handles:
    - Clean numbers: "23.5" → 23.5
    - Units attached: "23.5°C" → 23.5
    - Missing/invalid: "" or None → None
    """
    if not value or str(value).strip() == "":
        return None

    # Remove any non-numeric characters except decimal point and minus sign
    cleaned = re.sub(r'[^\d.\-]', '', str(value))

    try:
        temp = float(cleaned)
        # Sanity check: realistic temperature range for weather data
        if -50 <= temp <= 60:
            return round(temp, 1)
        else:
            logger.warning(f"Temperature out of realistic range: {value}")
            return None
    except ValueError:
        logger.warning(f"Could not parse temperature: {value}")
        return None


def clean_humidity(value):
    """
    Cleans humidity values.
    Handles:
    - Valid integers: "75" → 75
    - Invalid negatives: -1 → None
    - Missing: "" → None
    """
    if value is None or str(value).strip() == "":
        return None

    try:
        humidity = int(value)
        # Humidity must be between 0 and 100
        if 0 <= humidity <= 100:
            return humidity
        else:
            logger.warning(f"Humidity out of valid range (0-100): {value}")
            return None
    except (ValueError, TypeError):
        logger.warning(f"Could not parse humidity: {value}")
        return None


def clean_timestamp(value):
    """
    Standardises timestamps to ISO format: YYYY-MM-DD HH:MM:SS
    Handles:
    - Correct format: "2026-06-15 10:00:00" → kept as-is
    - Inconsistent format: "15/06/2026" → "2026-06-15 00:00:00"
    - Missing: "" → None
    """
    if not value or str(value).strip() == "":
        return None

    # Try standard format first
    formats = [
        "%Y-%m-%d %H:%M:%S",  # 2026-06-15 10:00:00
        "%d/%m/%Y",            # 15/06/2026
        "%Y-%m-%d",            # 2026-06-15
        "%d-%m-%Y",            # 15-06-2026
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(str(value).strip(), fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    logger.warning(f"Could not parse timestamp: {value}")
    return None


def process_row(row):
    """
    Cleans a single row from the CSV.
    Returns cleaned row dict, or None if the row is too broken to use.
    """
    city = str(row.get('city', '')).strip()
    temperature = clean_temperature(row.get('temperature'))
    humidity = clean_humidity(row.get('humidity'))
    timestamp = clean_timestamp(row.get('timestamp'))

    # If critical fields are missing, skip the row
    if not city or timestamp is None:
        logger.warning(f"Skipping row — missing critical fields: {row}")
        return None

    return {
        'city': city,
        'temperature': temperature if temperature is not None else 'NULL',
        'humidity': humidity if humidity is not None else 'NULL',
        'timestamp': timestamp,
        'data_quality': 'complete' if all([temperature, humidity]) else 'partial'
    }


def lambda_handler(event, context):
    """
    Main Lambda function.
    Triggered by S3 PUT event when a file is uploaded to the raw bucket.
    """
    logger.info(f"Event received: {json.dumps(event)}")

    # Track statistics for this run
    stats = {
        'total_rows': 0,
        'cleaned_rows': 0,
        'skipped_rows': 0,
        'files_processed': 0
    }

    # Loop through all files in the event
    # (Usually one file per trigger, but good practice to handle multiple)
    for record in event['Records']:
        source_bucket = record['s3']['bucket']['name']
        file_key = record['s3']['object']['key']

        logger.info(f"Processing file: s3://{source_bucket}/{file_key}")

        try:
            # Step 1 — Read the file from raw S3 bucket
            response = s3.get_object(Bucket=source_bucket, Key=file_key)
            raw_content = response['Body'].read().decode('utf-8', errors='replace')
            logger.info(f"File read successfully — {len(raw_content)} bytes")

            # Step 2 — Parse CSV
            reader = csv.DictReader(StringIO(raw_content))
            cleaned_rows = []

            for row in reader:
                stats['total_rows'] += 1
                cleaned = process_row(row)
                if cleaned:
                    cleaned_rows.append(cleaned)
                    stats['cleaned_rows'] += 1
                else:
                    stats['skipped_rows'] += 1

            logger.info(f"Cleaning complete — {stats['cleaned_rows']}/{stats['total_rows']} rows kept")

            # Step 3 — Write cleaned data to processed bucket
            if cleaned_rows:
                output = StringIO()
                fieldnames = ['city', 'temperature', 'humidity', 'timestamp', 'data_quality']
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(cleaned_rows)

                # Build destination key
                # e.g. weather_day1.csv → processed/weather_day1_cleaned.csv
                filename = file_key.split('/')[-1].replace('.csv', '_cleaned.csv')
                destination_key = f"processed/{filename}"

                # Get processed bucket name from environment or derive it
                processed_bucket = source_bucket.replace('raw', 'processed')

                s3.put_object(
                    Bucket=processed_bucket,
                    Key=destination_key,
                    Body=output.getvalue(),
                    ContentType='text/csv'
                )

                logger.info(f"Cleaned file written to s3://{processed_bucket}/{destination_key}")
                stats['files_processed'] += 1

            else:
                logger.warning(f"No valid rows after cleaning — file skipped")

        except Exception as e:
            logger.error(f"Error processing {file_key}: {str(e)}")
            # Re-raise so CloudWatch alarm triggers on Lambda error
            raise e

    logger.info(f"Pipeline run complete. Stats: {json.dumps(stats)}")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Pipeline complete',
            'stats': stats
        })
    }