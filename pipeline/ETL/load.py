"""Upload partitioned parquet files to S3 using AWS Wrangler."""

import awswrangler as wr
import pandas as pd

BUCKET_NAME = 'c20-lorenzo-t3-data-lake'


def upload_dimensions(bucket_name):
    """Upload dimension tables to S3. These are small tables that rarely change (trucks, payment methods)."""
    print("Uploading dimension tables...")

    # Read local parquet files
    trucks = pd.read_parquet('data/dimensions/dim_trucks.parquet')
    payment_methods = pd.read_parquet(
        'data/dimensions/dim_payment_methods.parquet')

    # Upload trucks dimension
    # S3 path format: s3://bucket-name/folder/file.parquet
    wr.s3.to_parquet(
        df=trucks,
        path=f's3://{bucket_name}/dimensions/dim_trucks.parquet'
    )
    print(f"✓ Uploaded {len(trucks)} trucks")

    # Upload payment methods dimension
    wr.s3.to_parquet(
        df=payment_methods,
        path=f's3://{bucket_name}/dimensions/dim_payment_methods.parquet'
    )
    print(f"✓ Uploaded {len(payment_methods)} payment methods")


def upload_partitioned_transactions(bucket_name):
    """Upload time-partitioned transaction data to S3 from the cleaned CSV."""
    print("\nUploading partitioned transaction data...")

    # Read from the CLEANED CSV (current batch only)
    df = pd.read_csv('data/transactions_cleaned.csv')
    df['at'] = pd.to_datetime(df['at'])  # Ensure datetime type

    print(f"Loaded {len(df)} transactions from current batch")

    # Add partition columns
    df['year'] = df['at'].dt.year
    df['month'] = df['at'].dt.month
    df['day'] = df['at'].dt.day

    # Upload to S3 with partitioning (append mode)
    wr.s3.to_parquet(
        df=df,
        path=f's3://{bucket_name}/transactions/',
        dataset=True,
        partition_cols=['year', 'month', 'day'],
        mode='append'  # Add to existing data in S3
    )

    print(f"✓ Uploaded {len(df)} transactions in partitioned format")


def verify_upload(bucket_name):
    """Check what files exist in the S3 bucket."""
    print("\nVerifying S3 bucket contents...")

    # List all files in the bucket
    files = wr.s3.list_objects(f's3://{bucket_name}/')

    print(f"\nFound {len(files)} files in S3:")
    for file in files[:10]:  # Show first 10 files
        print(f"  {file}")

    if len(files) > 10:
        print(f"  ... and {len(files) - 10} more files")


def upload_transaction_data(upload_dimensions=False):
    """Uploads transaction data to the database."""
    print("="*60)
    print("T3 Data Lake - Upload to S3")
    print("="*60)
    print(f"\nTarget bucket: {BUCKET_NAME}\n")

    # Check AWS credentials are configured
    try:
        # Conditionally upload dimension tables
        if upload_dimensions:
            print("⚠️  Uploading dimension tables (upload_dims=True)")
            upload_dimensions(BUCKET_NAME)
        else:
            print("ℹ️  Skipping dimension upload (upload_dims=False)")
            print("   Dimensions are uploaded only when they change\n")

        # Upload partitioned transactions
        upload_partitioned_transactions(BUCKET_NAME)

        # Verify upload
        verify_upload(BUCKET_NAME)

        print("\n" + "="*60)
        print("Upload complete!")
        print("="*60)

    except NotImplementedError as e:
        print(f"\n✗ Error: {e}")
        print("\nMake sure:")
        print("1. AWS credentials are configured (aws configure)")
        print("2. The S3 bucket exists (run terraform apply)")
        print("3. You have permission to write to the bucket")


if __name__ == "__main__":

    upload_transaction_data()
