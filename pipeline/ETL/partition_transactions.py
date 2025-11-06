import pandas as pd
import os


def load_cleaned_data(filepath='data/transactions_cleaned.csv'):
    """Load the cleaned transaction data."""
    df = pd.read_csv(filepath)
    df['at'] = pd.to_datetime(df['at'])
    return df


def extract_dimension_tables(df):
    """Extract dimension tables from the main dataframe."""
    trucks = df[['truck_id', 'truck_name', 'truck_description',
                 'has_card_reader', 'fsa_rating']].drop_duplicates()
    payment_methods = df[['payment_method_id',
                          'payment_method']].drop_duplicates()
    return trucks, payment_methods


def save_dimensions(trucks, payment_methods, folder='data/dimensions'):
    """Save dimension tables as parquet files."""
    os.makedirs(folder, exist_ok=True)

    trucks.to_parquet(f'{folder}/dim_trucks.parquet', index=False)
    print(f"Saved {len(trucks)} trucks to {folder}/dim_trucks.parquet")

    payment_methods.to_parquet(
        f'{folder}/dim_payment_methods.parquet', index=False)
    print(
        f"Saved {len(payment_methods)} payment methods to {folder}/dim_payment_methods.parquet")


def partition_transactions(df, base_folder='data/transactions'):
    """Partition transaction data by year/month/day."""

    # Extract date components
    df['year'] = df['at'].dt.year
    df['month'] = df['at'].dt.month
    df['day'] = df['at'].dt.day

    # Group by date and save each partition
    grouped = df.groupby(['year', 'month', 'day'])
    total_partitions = 0

    for (year, month, day), group in grouped:
        # Create folder path
        folder = f"{base_folder}/year={year}/month={month:02d}/day={day:02d}"
        os.makedirs(folder, exist_ok=True)

        # Drop the partition columns before saving
        partition_df = group.drop(columns=['year', 'month', 'day'])

        # Save to parquet
        filepath = f"{folder}/transactions.parquet"
        partition_df.to_parquet(filepath, index=False)

        total_partitions += 1
        print(f"Saved {len(partition_df)} transactions to {filepath}")

    return total_partitions


def main_partition_transactions():
    """Main function to run the partitioning process."""
    print("Loading cleaned data...\n")
    df = load_cleaned_data()

    print(f"Total transactions: {len(df)}")
    print(f"Date range: {df['at'].min()} to {df['at'].max()}\n")

    # Save dimension tables
    print("Saving dimension tables...")
    trucks, payment_methods = extract_dimension_tables(df)
    save_dimensions(trucks, payment_methods)

    # Partition transaction data
    print("\nPartitioning transaction data...")
    total = partition_transactions(df)

    print(
        f"\nComplete! Created {total} transaction partitions and 2 dimension tables.")

    return total


if __name__ == "__main__":
    main_partition_transactions()
