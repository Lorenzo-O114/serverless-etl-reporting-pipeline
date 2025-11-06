-- T3 Data Lake - Athena SQL Queries
-- Run these in AWS Athena console to explore the data

-- ========== BASIC EXPLORATION ==========

-- Show all tables in the database
SHOW TABLES;

-- Preview transaction data
SELECT * FROM transactions LIMIT 10;

-- Check table schema
DESCRIBE transactions;


-- ========== REVENUE ANALYSIS ==========

-- Total revenue across all trucks
SELECT 
    SUM(total) as total_revenue,
    COUNT(*) as total_transactions,
    AVG(total) as avg_transaction
FROM transactions;

-- Revenue by truck (top performers)
SELECT 
    truck_name,
    COUNT(*) as total_transactions,
    SUM(total) as total_revenue,
    AVG(total) as avg_transaction_value,
    ROUND(SUM(total) / (SELECT SUM(total) FROM transactions) * 100, 2) as revenue_percentage
FROM transactions
GROUP BY truck_name
ORDER BY total_revenue DESC;

-- Revenue by payment method
SELECT 
    payment_method,
    COUNT(*) as transactions,
    SUM(total) as revenue,
    ROUND(AVG(total), 2) as avg_value
FROM transactions
GROUP BY payment_method
ORDER BY revenue DESC;


-- ========== TIME-BASED ANALYSIS ==========

-- Daily revenue trend
SELECT 
    year,
    month,
    day,
    COUNT(*) as transactions,
    ROUND(SUM(total), 2) as daily_revenue,
    ROUND(AVG(total), 2) as avg_transaction
FROM transactions
GROUP BY year, month, day
ORDER BY year, month, day;

-- Hourly transaction patterns (busiest hours)
SELECT 
    HOUR(at) as hour_of_day,
    COUNT(*) as transactions,
    ROUND(SUM(total), 2) as revenue
FROM transactions
GROUP BY HOUR(at)
ORDER BY hour_of_day;

-- Day of week analysis
SELECT 
    DATE_FORMAT(at, '%W') as day_of_week,
    COUNT(*) as transactions,
    ROUND(SUM(total), 2) as revenue
FROM transactions
GROUP BY DATE_FORMAT(at, '%W')
ORDER BY revenue DESC;


-- ========== TRUCK PERFORMANCE ==========

-- Best performing truck by day
SELECT 
    year,
    month, 
    day,
    truck_name,
    COUNT(*) as transactions,
    ROUND(SUM(total), 2) as revenue
FROM transactions
GROUP BY year, month, day, truck_name
ORDER BY year, month, day, revenue DESC;

-- Trucks with card reader vs without
SELECT 
    has_card_reader,
    COUNT(DISTINCT truck_name) as num_trucks,
    COUNT(*) as transactions,
    ROUND(SUM(total), 2) as revenue
FROM transactions
GROUP BY has_card_reader;

-- FSA rating impact on revenue
SELECT 
    fsa_rating,
    COUNT(DISTINCT truck_name) as num_trucks,
    COUNT(*) as transactions,
    ROUND(AVG(total), 2) as avg_transaction,
    ROUND(SUM(total), 2) as total_revenue
FROM transactions
GROUP BY fsa_rating
ORDER BY fsa_rating DESC;


-- ========== DIMENSION TABLES ==========

-- View all trucks
SELECT * FROM dim_trucks;

-- View all payment methods  
SELECT * FROM dim_payment_methods;

-- Truck details with transaction counts
SELECT 
    t.truck_id,
    t.truck_name,
    t.truck_description,
    t.fsa_rating,
    t.has_card_reader,
    COUNT(*) as transaction_count
FROM dim_trucks t
LEFT JOIN transactions tr ON t.truck_id = tr.truck_id
GROUP BY t.truck_id, t.truck_name, t.truck_description, t.fsa_rating, t.has_card_reader
ORDER BY transaction_count DESC;


-- ========== BUSINESS INSIGHTS ==========

-- Peak hours for each truck
SELECT 
    truck_name,
    HOUR(at) as peak_hour,
    COUNT(*) as transactions
FROM transactions
GROUP BY truck_name, HOUR(at)
ORDER BY truck_name, transactions DESC;

-- High value transactions (above £10)
SELECT 
    truck_name,
    at,
    total,
    payment_method
FROM transactions
WHERE total > 10.00
ORDER BY total DESC
LIMIT 20;

-- Card vs cash preference by truck
SELECT 
    truck_name,
    payment_method,
    COUNT(*) as transactions,
    ROUND(SUM(total), 2) as revenue
FROM transactions
GROUP BY truck_name, payment_method
ORDER BY truck_name, transactions DESC;