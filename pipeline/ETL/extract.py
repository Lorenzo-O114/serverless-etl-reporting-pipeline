"""Extract transaction data from the transactional database."""

import json
import os
import boto3
import pandas as pd
import pymysql
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

# S3 configuration
S3_BUCKET = 'c20-lorenzo-t3-data-lake'
STATE_FILE_KEY = 'pipeline-state/last_run.txt'


def get_secret(secret_name='t3/database', region_name='eu-west-2'):
    """Retrieve database credentials from AWS Secrets Manager."""
    client = boto3.client('secretsmanager', region_name=region_name)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])


def get_db_connection():
    """Connect to database using credentials from Secrets Manager."""
    secrets = get_secret()

    return pymysql.connect(
        host=secrets['DB_HOST'],
        port=int(secrets['DB_PORT']),
        user=secrets['DB_USER'],
        password=secrets['DB_PASSWORD'],
        database=secrets['DB_NAME']
    )


def get_last_processed_timestamp():
    """
    Retrieve the last processed timestamp from S3 and add 1 second.
    Returns None if this is the first run.
    """

    s3_client = boto3.client('s3')

    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=STATE_FILE_KEY)
        timestamp_str = response['Body'].read().decode('utf-8').strip()

        print(f"Found last processed timestamp in S3: {timestamp_str}")

        # Convert to datetime, add 1 second to avoid boundary issues
        dt = datetime.fromisoformat(timestamp_str)
        dt = dt + timedelta(seconds=1)
        adjusted_timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')

        print(f"Adjusted timestamp for query: {adjusted_timestamp}")

        return adjusted_timestamp

    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print("No previous state found - this is the first run")
            return None
        else:
            print(f"Error reading state file: {e}")
            raise


def save_last_processed_timestamp(timestamp):
    """Save the latest processed timestamp to S3."""
    s3_client = boto3.client('s3')

    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=STATE_FILE_KEY,
            Body=str(timestamp).encode('utf-8')
        )
        print(f"Saved last processed timestamp to S3: {timestamp}")
    except ClientError as e:
        print(f"Error saving state file: {e}")
        raise


def extract_data(db_connection, since_timestamp=None):
    """Extract transaction data with joined dimension tables."""
    query = """
    SELECT 
        ft.transaction_id,
        ft.at,
        ft.total,
        ft.truck_id,
        ft.payment_method_id,
        dt.truck_name,
        dt.truck_description,
        dt.has_card_reader,
        dt.fsa_rating,
        pm.payment_method
    FROM FACT_Transaction ft
    JOIN DIM_Truck dt ON ft.truck_id = dt.truck_id
    JOIN DIM_Payment_Method pm ON ft.payment_method_id = pm.payment_method_id
    """

    # Add WHERE clause for incremental loading
    if since_timestamp:
        query += f" WHERE ft.at > '{since_timestamp}'"

    query += " ORDER BY ft.at"  # Important for tracking latest timestamp

    return pd.read_sql(query, db_connection)


def save_data(dataframe, filepath='data/transactions.csv'):
    """Save dataframe to CSV file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    dataframe.to_csv(filepath, index=False)


def main_extract():
    """Main extraction function that returns number of rows extracted."""
    print("="*60)
    print("EXTRACT: Getting data from RDS")
    print("="*60 + "\n")

    db_connection = get_db_connection()

    # Get last processed timestamp from S3
    last_timestamp = get_last_processed_timestamp()

    if last_timestamp:
        print(f"Extracting data since: {last_timestamp}")
    else:
        print("First run - extracting all available data")

    # Extract only new data
    transactions_df = extract_data(db_connection, last_timestamp)
    db_connection.close()

    if len(transactions_df) > 0:
        save_data(transactions_df)

        # Save the latest timestamp to S3 for next run
        latest_timestamp = transactions_df['at'].max()
        save_last_processed_timestamp(latest_timestamp)

        print(f"\n✓ Extracted {len(transactions_df)} new transactions")
        print(f"  Latest timestamp: {latest_timestamp}")
        print(f"  Saved to: data/transactions.csv")
    else:
        print("\nNo new transactions found")

    return len(transactions_df)


if __name__ == "__main__":
    main_extract()
