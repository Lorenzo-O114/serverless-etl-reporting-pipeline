from extract import main_extract
from transform import main_transform
from partition_transactions import main_partition_transactions
from load import upload_transaction_data

if __name__ == "__main__":
    print("\nStarting ETL Pipeline...\n")

    print("Step 1: Extracting data")
    rows_extracted = main_extract()

    # Exit early if no new data
    if rows_extracted == 0:
        print("\n" + "="*60)
        print("No new transactions found. Pipeline exiting.")
        print("="*60)
    else:
        print("\nStep 2: Transforming data")
        main_transform()

        print("\nStep 3: Partitioning transactions (local backup)")
        main_partition_transactions()

        print("\nStep 4: Loading data to S3")
        upload_transaction_data(upload_dimensions=False)

        print("\n" + "="*60)
        print("ETL Pipeline completed successfully!")
        print(f"Processed {rows_extracted} new transactions")
        print("="*60)
