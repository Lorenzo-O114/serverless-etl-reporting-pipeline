import pandas as pd
import os


def load_data(filepath='data/transactions.csv'):
    """Load the extracted transaction data."""
    return pd.read_csv(filepath)


def clean_data(df):
    """Clean and transform the transaction data."""
    print(f"Initial rows: {len(df)}")

    # Remove rows where total is zero, blank, or NULL
    df = df[df['total'].notna()]
    df = df[df['total'] != 0]

    print(f"After removing invalid totals: {len(df)}")

    # Convert total to float and divide by 100 (stored as pence/cents)
    df['total'] = df['total'].astype(float) / 100

    # Convert 'at' column to datetime
    df['at'] = pd.to_datetime(df['at'])

    # Convert boolean column
    df['has_card_reader'] = df['has_card_reader'].astype(bool)

    # Remove any fully duplicate rows
    duplicate_check_cols = ['at', 'truck_id', 'payment_method_id', 'total']

    duplicates = df[df.duplicated(subset=duplicate_check_cols, keep=False)]

    if len(duplicates) > 0:
        print(
            f"Warning: Found {len(duplicates)} potential duplicate transactions")
        df = df.drop_duplicates(subset=duplicate_check_cols, keep='first')

    # Remove rows with any remaining NULL values in critical columns
    critical_columns = ['transaction_id', 'at',
                        'total', 'truck_id', 'payment_method_id']
    df = df.dropna(subset=critical_columns)

    print(f"Final rows: {len(df)}")

    return df


def save_cleaned_data(df, filepath='data/transactions_cleaned.csv'):
    """Save the cleaned transaction data."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    df.to_csv(filepath, index=False)


def main_transform():
    """Main function to run the transformation process."""
    df = load_data()
    df_cleaned = clean_data(df)
    save_cleaned_data(df_cleaned)

    print(f"\nCleaned data saved to data/transactions_cleaned.csv")
    print(f"Date range: {df_cleaned['at'].min()} to {df_cleaned['at'].max()}")
    print(f"Total revenue: £{df_cleaned['total'].sum():,.2f}")

    return len(df_cleaned)


if __name__ == "__main__":
    main_transform()
