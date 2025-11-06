"""
Lambda function to generate daily T3 transaction report.
Reads yesterday's data from S3 and generates HTML report.
"""

import json
from datetime import datetime, timedelta
import boto3
import pandas as pd
import pyarrow.parquet as pq
import io

# Configuration
S3_BUCKET = 'c20-lorenzo-t3-data-lake'
REPORT_OUTPUT_PREFIX = 'reports'


def get_yesterday_date():
    """Get yesterday's date in YYYY-MM-DD format."""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')


def load_yesterday_transactions():
    """Load yesterday's transactions from S3 Data Lake using boto3."""
    yesterday = datetime.now() - timedelta(days=1)
    year = yesterday.year
    month = yesterday.month
    day = yesterday.day

    # S3 path for yesterday's partition
    prefix = f'transactions/year={year}/month={month}/day={day}/'

    print(f"Reading from: s3://{S3_BUCKET}/{prefix}")

    s3_client = boto3.client('s3')

    try:
        # List all parquet files in the partition
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)

        if 'Contents' not in response:
            print("No files found")
            return pd.DataFrame()

        # Read all parquet files
        dfs = []
        for obj in response['Contents']:
            if obj['Key'].endswith('.parquet'):
                print(f"Reading: {obj['Key']}")
                file_obj = s3_client.get_object(
                    Bucket=S3_BUCKET, Key=obj['Key'])
                table = pq.read_table(io.BytesIO(file_obj['Body'].read()))
                dfs.append(table.to_pandas())

        if dfs:
            df = pd.concat(dfs, ignore_index=True)
            print(f"Loaded {len(df)} transactions")
            return df

        return pd.DataFrame()

    except Exception as e:
        print(f"Error loading data: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def calculate_metrics(df):
    """Calculate report metrics from transaction data."""
    if df.empty:
        return {
            'date': get_yesterday_date(),
            'total_revenue': 0,
            'total_transactions': 0,
            'best_truck': 'N/A',
            'best_truck_revenue': 0,
            'worst_truck': 'N/A',
            'worst_truck_revenue': 0,
            'payment_methods': {},
            'average_transaction': 0,
            'all_trucks': []
        }

    # Total metrics
    total_revenue = df['total'].sum()
    total_transactions = len(df)
    average_transaction = df['total'].mean()

    # Truck performance (detailed)
    truck_stats = df.groupby('truck_name').agg({
        'total': ['sum', 'count', 'mean']
    }).round(2)
    truck_stats.columns = ['revenue', 'transactions', 'avg_transaction']
    truck_stats = truck_stats.sort_values('revenue', ascending=False)

    best_truck = truck_stats.index[0]
    best_truck_revenue = truck_stats.loc[best_truck, 'revenue']
    worst_truck = truck_stats.index[-1]
    worst_truck_revenue = truck_stats.loc[worst_truck, 'revenue']

    # All trucks data for detailed table
    all_trucks = [
        {
            'name': truck,
            'revenue': float(row['revenue']),
            'transactions': int(row['transactions']),
            'avg_transaction': float(row['avg_transaction'])
        }
        for truck, row in truck_stats.iterrows()
    ]

    # Payment method breakdown (with cost implications)
    payment_breakdown = df.groupby('payment_method').agg({
        'total': ['count', 'sum']
    })
    payment_breakdown.columns = ['count', 'revenue']

    # Assume 2% card processing fee (industry standard)
    CARD_FEE_RATE = 0.02

    payment_methods = {}
    for method in payment_breakdown.index:
        count = int(payment_breakdown.loc[method, 'count'])
        revenue = float(payment_breakdown.loc[method, 'revenue'])
        percentage = (revenue / total_revenue *
                      100) if total_revenue > 0 else 0

        # Estimate processing costs for card payments
        processing_cost = revenue * CARD_FEE_RATE if 'card' in method.lower() else 0

        payment_methods[method] = {
            'count': count,
            'revenue': revenue,
            'percentage': percentage,
            'processing_cost': processing_cost
        }

    # Calculate total card processing costs
    total_card_costs = sum(pm['processing_cost']
                           for pm in payment_methods.values())

    return {
        'date': get_yesterday_date(),
        'total_revenue': total_revenue,
        'total_transactions': total_transactions,
        'best_truck': best_truck,
        'best_truck_revenue': best_truck_revenue,
        'worst_truck': worst_truck,
        'worst_truck_revenue': worst_truck_revenue,
        'payment_methods': payment_methods,
        'average_transaction': average_transaction,
        'all_trucks': all_trucks,
        'total_card_costs': total_card_costs,
        'net_revenue': total_revenue - total_card_costs
    }


def generate_html_report(metrics):
    """Generate HTML report from metrics with CFO focus."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>T3 Daily Report - {metrics['date']}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 1000px;
                margin: 40px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .header {{
                background-color: #2c3e50;
                color: white;
                padding: 20px;
                border-radius: 5px;
                margin-bottom: 20px;
            }}
            .kpi-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-bottom: 20px;
            }}
            .metric-card {{
                background-color: white;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .metric-title {{
                font-size: 12px;
                color: #7f8c8d;
                text-transform: uppercase;
                margin-bottom: 5px;
                font-weight: bold;
            }}
            .metric-value {{
                font-size: 28px;
                font-weight: bold;
                color: #2c3e50;
            }}
            .metric-subtitle {{
                font-size: 14px;
                color: #95a5a6;
                margin-top: 5px;
            }}
            .best {{ border-left: 4px solid #27ae60; }}
            .worst {{ border-left: 4px solid #e74c3c; }}
            .cost {{ border-left: 4px solid #f39c12; }}
            .profit {{ border-left: 4px solid #16a085; }}
            .data-table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
                background: white;
            }}
            .data-table th, .data-table td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ecf0f1;
            }}
            .data-table th {{
                background-color: #34495e;
                color: white;
                font-weight: bold;
            }}
            .data-table tr:hover {{
                background-color: #f8f9fa;
            }}
            .highlight-cost {{
                color: #e74c3c;
                font-weight: bold;
            }}
            .section-title {{
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                margin: 30px 0 15px 0;
                padding-bottom: 10px;
                border-bottom: 2px solid #3498db;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #ecf0f1;
                color: #7f8c8d;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🚚 T3 Food Trucks - Daily Financial Report</h1>
            <p><strong>Report Date:</strong> {metrics['date']}</p>
            <p style="font-size: 14px; opacity: 0.9;">Prepared for: Hiram Boulie, CFO</p>
        </div>
        
        <!-- Key Performance Indicators -->
        <div class="kpi-grid">
            <div class="metric-card profit">
                <div class="metric-title">💰 Total Revenue</div>
                <div class="metric-value">£{metrics['total_revenue']:,.2f}</div>
                <div class="metric-subtitle">{metrics['total_transactions']} transactions</div>
            </div>
            
            <div class="metric-card cost">
                <div class="metric-title">💳 Card Processing Costs</div>
                <div class="metric-value highlight-cost">-£{metrics['total_card_costs']:,.2f}</div>
                <div class="metric-subtitle">~2% of card payments</div>
            </div>
            
            <div class="metric-card profit">
                <div class="metric-title">📊 Net Revenue</div>
                <div class="metric-value">£{metrics['net_revenue']:,.2f}</div>
                <div class="metric-subtitle">After processing fees</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-title">📈 Avg Transaction</div>
                <div class="metric-value">£{metrics['average_transaction']:.2f}</div>
            </div>
        </div>
        
        <!-- Best/Worst Performers -->
        <div class="kpi-grid" style="grid-template-columns: 1fr 1fr;">
            <div class="metric-card best">
                <div class="metric-title">🏆 Top Performer</div>
                <h2 style="margin: 10px 0;">{metrics['best_truck']}</h2>
                <div class="metric-value">£{metrics['best_truck_revenue']:,.2f}</div>
            </div>
            
            <div class="metric-card worst">
                <div class="metric-title">⚠️ Needs Attention</div>
                <h2 style="margin: 10px 0;">{metrics['worst_truck']}</h2>
                <div class="metric-value">£{metrics['worst_truck_revenue']:,.2f}</div>
            </div>
        </div>
        
        <!-- All Trucks Performance Table -->
        <div class="section-title">📊 Truck Performance Breakdown</div>
        <div class="metric-card">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Truck Name</th>
                        <th>Revenue</th>
                        <th>Transactions</th>
                        <th>Avg per Transaction</th>
                        <th>% of Total</th>
                    </tr>
                </thead>
                <tbody>
    """

    # Add truck rows
    for truck in metrics['all_trucks']:
        pct_of_total = (truck['revenue'] / metrics['total_revenue']
                        * 100) if metrics['total_revenue'] > 0 else 0
        html += f"""
                    <tr>
                        <td><strong>{truck['name']}</strong></td>
                        <td>£{truck['revenue']:,.2f}</td>
                        <td>{truck['transactions']}</td>
                        <td>£{truck['avg_transaction']:.2f}</td>
                        <td>{pct_of_total:.1f}%</td>
                    </tr>
        """

    html += """
                </tbody>
            </table>
        </div>
        
        <!-- Payment Methods -->
        <div class="section-title">💳 Payment Method Analysis</div>
        <div class="metric-card">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Payment Method</th>
                        <th>Transactions</th>
                        <th>Revenue</th>
                        <th>Processing Cost</th>
                        <th>% of Total</th>
                    </tr>
                </thead>
                <tbody>
    """

    # Add payment method rows
    for method, stats in metrics['payment_methods'].items():
        cost_display = f"£{stats['processing_cost']:.2f}" if stats[
            'processing_cost'] > 0 else "£0.00 (Free)"
        html += f"""
                    <tr>
                        <td><strong>{method}</strong></td>
                        <td>{stats['count']}</td>
                        <td>£{stats['revenue']:,.2f}</td>
                        <td class="{'highlight-cost' if stats['processing_cost'] > 0 else ''}">{cost_display}</td>
                        <td>{stats['percentage']:.1f}%</td>
                    </tr>
        """

    html += f"""
                </tbody>
            </table>
            <p style="margin-top: 15px; font-size: 13px; color: #7f8c8d;">
                <strong>Note:</strong> Card processing typically costs 2% per transaction. 
                Total processing costs yesterday: <span class="highlight-cost">£{metrics['total_card_costs']:.2f}</span>
            </p>
        </div>
        
        <div class="footer">
            <p><strong>T3 Data Pipeline</strong> | Automated Daily Report</p>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            <p>For questions, contact the data team</p>
        </div>
    </body>
    </html>
    """

    return html


def save_report_to_s3(html_content, metrics):
    """Save HTML report to S3."""
    s3_client = boto3.client('s3')

    # Generate filename with date
    date_str = metrics['date']
    filename = f"{REPORT_OUTPUT_PREFIX}/daily-report-{date_str}.html"

    # Upload to S3
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=filename,
        Body=html_content.encode('utf-8'),
        ContentType='text/html'
    )

    print(f"Report saved to s3://{S3_BUCKET}/{filename}")
    return f"s3://{S3_BUCKET}/{filename}"


def lambda_handler(event, context):
    """Main Lambda handler function."""
    try:
        print("Starting report generation...")

        # Load yesterday's data
        df = load_yesterday_transactions()

        if df.empty:
            return {
                'statusCode': 404,
                'body': json.dumps({'message': 'No data found for yesterday'})
            }

        # Calculate metrics
        metrics = calculate_metrics(df)
        print(
            f"Calculated metrics: {metrics['total_transactions']} transactions, £{metrics['total_revenue']:.2f} revenue")

        # Generate HTML report
        html_report = generate_html_report(metrics)

        # Save to S3
        report_location = save_report_to_s3(html_report, metrics)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Report generated successfully',
                'report_location': report_location,
                'date': metrics['date'],
                'total_revenue': metrics['total_revenue'],
                'total_transactions': metrics['total_transactions'],
                'html_content': html_report
            })
        }

    except Exception as e:
        print(f"Error generating report: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


if __name__ == "__main__":
    # Test locally
    print("Testing report generation locally...\n")
    result = lambda_handler({}, {})
    print(f"\nResult: {result}")
