"""T3 Food Trucks - Executive Dashboard
Displays transaction data and insights for stakeholders"""

import streamlit as st
import pandas as pd
import awswrangler as wr
import plotly.express as px
import plotly.graph_objects as go

# Page configuration
st.set_page_config(
    page_title="T3 Dashboard",
    page_icon="🚚",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Title and header
st.title("🚚 Tasty Truck Treats - Executive Dashboard")
st.markdown("Real-time insights from our food truck fleet across Lichfield")
st.markdown("---")

# Load data from S3


@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_transaction_data():
    """Load transaction data from S3 data lake."""
    bucket_name = "c20-lorenzo-t3-data-lake"

    df = wr.s3.read_parquet(
        path=f"s3://{bucket_name}/transactions/",
        dataset=True
    )

    df['at'] = pd.to_datetime(df['at'])
    df['date'] = df['at'].dt.date
    df['hour'] = df['at'].dt.hour
    df['day_name'] = df['at'].dt.day_name()

    return df


@st.cache_data(ttl=3600)
def load_dimension_tables():
    """Load dimension tables from S3."""
    bucket_name = "c20-lorenzo-t3-data-lake"

    trucks = wr.s3.read_parquet(
        f"s3://{bucket_name}/dimensions/dim_trucks.parquet")
    payment_methods = wr.s3.read_parquet(
        f"s3://{bucket_name}/dimensions/dim_payment_methods.parquet")

    return trucks, payment_methods


# Load data
with st.spinner("Loading data from data lake..."):
    df = load_transaction_data()
    trucks_dim, payment_dim = load_dimension_tables()

# Sidebar filters
st.sidebar.header("🔍 Filters")

# Date range filter
date_range = st.sidebar.date_input(
    "Select Date Range",
    value=(df['date'].min(), df['date'].max()),
    min_value=df['date'].min(),
    max_value=df['date'].max()
)

# Truck filter
selected_trucks = st.sidebar.multiselect(
    "Select Trucks",
    options=df['truck_name'].unique(),
    default=df['truck_name'].unique()
)

# Payment method filter
selected_payments = st.sidebar.multiselect(
    "Payment Methods",
    options=df['payment_method'].unique(),
    default=df['payment_method'].unique()
)

# Apply filters
if len(date_range) == 2:
    filtered_df = df[
        (df['date'] >= date_range[0]) &
        (df['date'] <= date_range[1]) &
        (df['truck_name'].isin(selected_trucks)) &
        (df['payment_method'].isin(selected_payments))
    ]
else:
    filtered_df = df[
        (df['truck_name'].isin(selected_trucks)) &
        (df['payment_method'].isin(selected_payments))
    ]

# ========== KEY METRICS (For Hiram - CFO) ==========
st.header("💰 Financial Overview")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Total Revenue", f"£{filtered_df['total'].sum():,.2f}")

with col2:
    st.metric("Total Transactions", f"{len(filtered_df):,}")

with col3:
    st.metric("Avg Transaction", f"£{filtered_df['total'].mean():.2f}")

with col4:
    daily_avg = filtered_df.groupby('date')['total'].sum().mean()
    st.metric("Avg Daily Revenue", f"£{daily_avg:,.2f}")

with col5:
    card_pct = (filtered_df['payment_method'] ==
                'card').sum() / len(filtered_df) * 100
    st.metric("Card Payment %", f"{card_pct:.1f}%")

st.markdown("---")

# ========== REVENUE TRENDS (For Hiram) ==========
st.header("📈 Revenue Trends")

col1, col2 = st.columns(2)

with col1:
    # Daily revenue trend
    daily_revenue = filtered_df.groupby('date')['total'].sum().reset_index()
    fig_daily = px.line(
        daily_revenue,
        x='date',
        y='total',
        title='Daily Revenue Trend',
        labels={'total': 'Revenue (£)', 'date': 'Date'}
    )
    fig_daily.update_traces(line_color='#1f77b4', line_width=3)
    st.plotly_chart(fig_daily, use_container_width=True)

with col2:
    # Hourly transaction pattern
    hourly_transactions = filtered_df.groupby(
        'hour').size().reset_index(name='count')
    fig_hourly = px.bar(
        hourly_transactions,
        x='hour',
        y='count',
        title='Transactions by Hour of Day',
        labels={'hour': 'Hour', 'count': 'Number of Transactions'}
    )
    fig_hourly.update_traces(marker_color='#ff7f0e')
    st.plotly_chart(fig_hourly, use_container_width=True)

st.markdown("---")

# ========== TRUCK PERFORMANCE (For Miranda - Head of Culinary) ==========
st.header("🚚 Truck Performance Analysis")

col1, col2 = st.columns(2)

with col1:
    # Revenue by truck
    truck_revenue = filtered_df.groupby(
        'truck_name')['total'].sum().sort_values(ascending=False).reset_index()
    fig_truck_rev = px.bar(
        truck_revenue,
        x='total',
        y='truck_name',
        orientation='h',
        title='Revenue by Truck',
        labels={'total': 'Total Revenue (£)', 'truck_name': 'Truck'},
        color='total',
        color_continuous_scale='Blues'
    )
    st.plotly_chart(fig_truck_rev, use_container_width=True)

with col2:
    # Transaction count by truck
    truck_transactions = filtered_df.groupby('truck_name').size(
    ).sort_values(ascending=False).reset_index(name='count')
    fig_truck_trans = px.bar(
        truck_transactions,
        x='count',
        y='truck_name',
        orientation='h',
        title='Transaction Volume by Truck',
        labels={'count': 'Number of Transactions', 'truck_name': 'Truck'},
        color='count',
        color_continuous_scale='Greens'
    )
    st.plotly_chart(fig_truck_trans, use_container_width=True)

# Average transaction value by truck
truck_avg = filtered_df.groupby('truck_name')['total'].mean(
).sort_values(ascending=False).reset_index()
fig_avg = px.bar(
    truck_avg,
    x='truck_name',
    y='total',
    title='Average Transaction Value by Truck (Price Point Analysis)',
    labels={'total': 'Average Transaction (£)', 'truck_name': 'Truck'},
    color='total',
    color_continuous_scale='Purples'
)
st.plotly_chart(fig_avg, use_container_width=True)

st.markdown("---")

# ========== PAYMENT ANALYSIS (For Miranda & Hiram) ==========
st.header("💳 Payment Method Analysis")

col1, col2, col3 = st.columns(3)

with col1:
    # Payment method distribution
    payment_counts = filtered_df['payment_method'].value_counts().reset_index()
    payment_counts.columns = ['payment_method', 'count']
    fig_payment = px.pie(
        payment_counts,
        values='count',
        names='payment_method',
        title='Payment Method Distribution',
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    st.plotly_chart(fig_payment, use_container_width=True)

with col2:
    # Revenue by payment method
    payment_revenue = filtered_df.groupby('payment_method')[
        'total'].sum().reset_index()
    fig_pay_rev = px.bar(
        payment_revenue,
        x='payment_method',
        y='total',
        title='Revenue by Payment Method',
        labels={'total': 'Revenue (£)', 'payment_method': 'Payment Method'},
        color='payment_method'
    )
    st.plotly_chart(fig_pay_rev, use_container_width=True)

with col3:
    # Payment preference by truck
    truck_payment = filtered_df.groupby(
        ['truck_name', 'payment_method']).size().reset_index(name='count')
    fig_truck_pay = px.bar(
        truck_payment,
        x='truck_name',
        y='count',
        color='payment_method',
        title='Payment Preferences by Truck',
        labels={'count': 'Transactions', 'truck_name': 'Truck'},
        barmode='group'
    )
    st.plotly_chart(fig_truck_pay, use_container_width=True)

st.markdown("---")

# ========== OPERATIONAL INSIGHTS (For Miranda) ==========
st.header("⏰ Operational Insights")

col1, col2 = st.columns(2)

with col1:
    # Day of week performance
    day_order = ['Monday', 'Tuesday', 'Wednesday',
                 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_revenue = filtered_df.groupby(
        'day_name')['total'].sum().reindex(day_order).reset_index()
    fig_day = px.bar(
        day_revenue,
        x='day_name',
        y='total',
        title='Revenue by Day of Week',
        labels={'total': 'Revenue (£)', 'day_name': 'Day'},
        color='total',
        color_continuous_scale='Teal'
    )
    st.plotly_chart(fig_day, use_container_width=True)

with col2:
    # Top performing days
    top_days = filtered_df.groupby('date').agg({
        'total': 'sum',
        'transaction_id': 'count'
    }).sort_values('total', ascending=False).head(10).reset_index()
    top_days.columns = ['Date', 'Revenue', 'Transactions']

    st.subheader("🏆 Top 10 Revenue Days")
    st.dataframe(
        top_days.style.format(
            {'Revenue': '£{:.2f}', 'Transactions': '{:,.0f}'}),
        hide_index=True,
        use_container_width=True
    )

st.markdown("---")

# ========== TRUCK DETAILS (For Miranda & Alexander) ==========
st.header("📋 Truck Details & Performance")

# Merge with dimension table for FSA ratings
truck_performance = filtered_df.groupby('truck_name').agg({
    'total': ['sum', 'mean', 'count'],
    'fsa_rating': 'first',
    'has_card_reader': 'first'
}).reset_index()

truck_performance.columns = ['Truck Name', 'Total Revenue',
                             'Avg Transaction', 'Transactions', 'FSA Rating', 'Card Reader']
truck_performance = truck_performance.sort_values(
    'Total Revenue', ascending=False)

st.dataframe(
    truck_performance.style.format({
        'Total Revenue': '£{:.2f}',
        'Avg Transaction': '£{:.2f}',
        'Transactions': '{:,.0f}'
    }),
    hide_index=True,
    use_container_width=True
)

st.markdown("---")

# ========== RAW DATA EXPLORER ==========
with st.expander("🔍 View Raw Transaction Data"):
    st.dataframe(
        filtered_df.sort_values('at', ascending=False).head(100),
        use_container_width=True,
        hide_index=True
    )

# Footer
st.markdown("---")
st.markdown("**Data Source:** AWS S3 Data Lake | **Last Updated:** Real-time")
st.markdown("*Dashboard built for T3 stakeholders: Hiram Boulie (CFO), Miranda Courcelle (Head of Culinary), Alexander D'Torre (Head of Technology)*")
