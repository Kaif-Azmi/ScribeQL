-- ScribeQL Demo Database Seed Data
-- Dialect: PostgreSQL

-- Categories
INSERT INTO demo.categories (id, name, slug, description) VALUES
(1, 'Electronics', 'electronics', 'Smartphones, laptops, audio gear, and electronic accessories'),
(2, 'Apparel & Fashion', 'apparel-fashion', 'Men and women clothing, footwear, and activewear'),
(3, 'Home & Kitchen', 'home-kitchen', 'Kitchen appliances, cookware, and home essentials'),
(4, 'Books & Stationery', 'books-stationery', 'Bestsellers, technical books, and notebooks'),
(5, 'Fitness & Sports', 'fitness-sports', 'Workout equipment, yoga mats, and sports gear')
ON CONFLICT (id) DO NOTHING;

-- Products
INSERT INTO demo.products (id, name, category_id, sku, price, cost_price, stock_quantity, is_active) VALUES
(1, 'Aura Wireless Noise-Cancelling Headphones', 1, 'ELEC-HDPH-001', 14999.00, 9500.00, 45, true),
(2, 'Zenith Mechanical Gaming Keyboard', 1, 'ELEC-KEYB-002', 4999.00, 3100.00, 80, true),
(3, 'UltraFast 65W GaN USB-C Charger', 1, 'ELEC-CHRG-003', 1999.00, 900.00, 150, true),
(4, 'SmartFit Pro Fitness Tracker Band', 1, 'ELEC-BAND-004', 3499.00, 2100.00, 60, true),
(5, 'Classic Oxford Cotton Shirt - Navy', 2, 'APP-SHRT-001', 2199.00, 950.00, 120, true),
(6, 'Breathable Tech Runner Sneakers', 2, 'APP-SHOE-002', 4299.00, 2200.00, 50, true),
(7, 'Vintage Denim Jacket', 2, 'APP-JCKT-003', 3799.00, 1800.00, 35, true),
(8, 'Ceramic Pour-Over Coffee Maker Set', 3, 'HOME-COFF-001', 2499.00, 1100.00, 40, true),
(9, 'Non-Stick Tri-Ply Stainless Steel Pan', 3, 'HOME-COOK-002', 3199.00, 1600.00, 75, true),
(10, 'Aroma Ultrasonic Diffuser', 3, 'HOME-DIFF-003', 1899.00, 850.00, 90, true),
(11, 'Designing Data-Intensive Applications', 4, 'BOOK-TECH-001', 1850.00, 1200.00, 110, true),
(12, 'Atomic Habits Hardcover Edition', 4, 'BOOK-SELF-002', 799.00, 400.00, 200, true),
(13, 'High-Density Non-Slip Yoga Mat', 5, 'FIT-YOGA-001', 1599.00, 700.00, 85, true),
(14, 'Adjustable Dumbbell Set (20kg)', 5, 'FIT-DUMB-002', 6499.00, 4100.00, 25, true)
ON CONFLICT (id) DO NOTHING;

-- Reset sequence for categories and products
SELECT setval('demo.categories_id_seq', (SELECT MAX(id) FROM demo.categories));
SELECT setval('demo.products_id_seq', (SELECT MAX(id) FROM demo.products));

-- Customers
INSERT INTO demo.customers (id, name, email, phone, city, state, country, created_at) VALUES
(1, 'Asha Verma', 'asha.verma@example.com', '+919876543210', 'Bengaluru', 'Karnataka', 'India', '2025-01-10 09:30:00+00'),
(2, 'Rohan Mehta', 'rohan.mehta@example.com', '+919876543211', 'Mumbai', 'Maharashtra', 'India', '2025-01-15 14:20:00+00'),
(3, 'Vikram Sharma', 'vikram.sharma@example.com', '+919876543212', 'Delhi', 'Delhi', 'India', '2025-02-01 11:00:00+00'),
(4, 'Ananya Patel', 'ananya.patel@example.com', '+919876543213', 'Ahmedabad', 'Gujarat', 'India', '2025-02-14 16:45:00+00'),
(5, 'Priya Nair', 'priya.nair@example.com', '+919876543214', 'Kochi', 'Kerala', 'India', '2025-02-20 10:15:00+00'),
(6, 'Kabir Sen', 'kabir.sen@example.com', '+919876543215', 'Kolkata', 'West Bengal', 'India', '2025-03-05 18:00:00+00'),
(7, 'Neha Rao', 'neha.rao@example.com', '+919876543216', 'Hyderabad', 'Telangana', 'India', '2025-03-12 12:30:00+00'),
(8, 'Arjun Gupta', 'arjun.gupta@example.com', '+919876543217', 'Pune', 'Maharashtra', 'India', '2025-04-01 08:45:00+00')
ON CONFLICT (id) DO NOTHING;

SELECT setval('demo.customers_id_seq', (SELECT MAX(id) FROM demo.customers));

-- Orders
INSERT INTO demo.orders (id, customer_id, order_date, status, subtotal, discount_amount, tax_amount, total, notes) VALUES
(1, 1, '2026-08-10 10:15:00+00', 'delivered', 19998.00, 1000.00, 3419.64, 22417.64, 'Please call before delivery'),
(2, 1, '2026-08-25 14:00:00+00', 'delivered', 22998.00, 1500.00, 3869.64, 25367.64, 'Leave at security desk'),
(3, 2, '2026-08-18 16:30:00+00', 'delivered', 38796.00, 2000.00, 6623.28, 43419.28, 'Urgent shipping requested'),
(4, 3, '2026-08-22 11:20:00+00', 'delivered', 7098.00, 500.00, 1187.64, 7785.64, NULL),
(5, 4, '2026-09-02 09:40:00+00', 'delivered', 4998.00, 0.00, 899.64, 5897.64, 'Gift wrap required'),
(6, 5, '2026-09-05 13:10:00+00', 'delivered', 14999.00, 500.00, 2609.82, 17108.82, NULL),
(7, 2, '2026-09-08 17:00:00+00', 'shipped', 2570.00, 0.00, 462.60, 3032.60, NULL),
(8, 6, '2026-09-12 15:25:00+00', 'processing', 6499.00, 300.00, 1115.82, 7314.82, NULL),
(9, 7, '2026-09-14 18:50:00+00', 'delivered', 3199.00, 200.00, 539.82, 3538.82, NULL),
(10, 8, '2026-09-15 12:05:00+00', 'cancelled', 4299.00, 0.00, 773.82, 5072.82, 'Customer cancelled order')
ON CONFLICT (id) DO NOTHING;

SELECT setval('demo.orders_id_seq', (SELECT MAX(id) FROM demo.orders));

-- Order Items
INSERT INTO demo.order_items (id, order_id, product_id, quantity, unit_price, total_price) VALUES
(1, 1, 1, 1, 14999.00, 14999.00),
(2, 1, 2, 1, 4999.00, 4999.00),
(3, 2, 1, 1, 14999.00, 14999.00),
(4, 2, 14, 1, 6499.00, 6499.00),
(5, 2, 3, 1, 1499.00, 1499.00),
(6, 3, 1, 2, 14999.00, 29998.00),
(7, 3, 6, 2, 4299.00, 8598.00),
(8, 4, 7, 1, 3799.00, 3799.00),
(9, 4, 9, 1, 3199.00, 3199.00),
(10, 4, 12, 1, 799.00, 799.00),
(11, 5, 8, 2, 2499.00, 4998.00),
(12, 6, 1, 1, 14999.00, 14999.00),
(13, 7, 11, 1, 1850.00, 1850.00),
(14, 7, 12, 1, 720.00, 720.00),
(15, 8, 14, 1, 6499.00, 6499.00),
(16, 9, 9, 1, 3199.00, 3199.00),
(17, 10, 6, 1, 4299.00, 4299.00)
ON CONFLICT (id) DO NOTHING;

SELECT setval('demo.order_items_id_seq', (SELECT MAX(id) FROM demo.order_items));

-- Payments
INSERT INTO demo.payments (id, order_id, payment_method, amount, status, transaction_ref, paid_at) VALUES
(1, 1, 'credit_card', 22417.64, 'completed', 'TXN_CC_9081231', '2026-08-10 10:16:30+00'),
(2, 2, 'upi', 25367.64, 'completed', 'TXN_UPI_8871234', '2026-08-25 14:02:10+00'),
(3, 3, 'net_banking', 43419.28, 'completed', 'TXN_NB_7719203', '2026-08-18 16:32:00+00'),
(4, 4, 'upi', 7785.64, 'completed', 'TXN_UPI_6619284', '2026-08-22 11:21:45+00'),
(5, 5, 'credit_card', 5897.64, 'completed', 'TXN_CC_5510293', '2026-09-02 09:41:20+00'),
(6, 6, 'upi', 17108.82, 'completed', 'TXN_UPI_4419281', '2026-09-05 13:12:00+00'),
(7, 7, 'debit_card', 3032.60, 'completed', 'TXN_DC_3319028', '2026-09-08 17:01:15+00'),
(8, 8, 'upi', 7314.82, 'completed', 'TXN_UPI_2219481', '2026-09-12 15:26:00+00'),
(9, 9, 'credit_card', 3538.82, 'completed', 'TXN_CC_1102938', '2026-09-14 18:51:30+00'),
(10, 10, 'cod', 5072.82, 'refunded', 'TXN_COD_0019283', '2026-09-15 12:05:00+00')
ON CONFLICT (id) DO NOTHING;

SELECT setval('demo.payments_id_seq', (SELECT MAX(id) FROM demo.payments));

-- Shipments
INSERT INTO demo.shipments (id, order_id, carrier, tracking_number, status, shipped_at, delivered_at) VALUES
(1, 1, 'BlueDart Express', 'BD-98127391', 'delivered', '2026-08-11 08:00:00+00', '2026-08-13 15:30:00+00'),
(2, 2, 'Delhivery', 'DL-88192831', 'delivered', '2026-08-26 09:00:00+00', '2026-08-28 17:45:00+00'),
(3, 3, 'BlueDart Express', 'BD-77192831', 'delivered', '2026-08-19 08:30:00+00', '2026-08-21 14:20:00+00'),
(4, 4, 'DTDC', 'DT-66192839', 'delivered', '2026-08-23 10:00:00+00', '2026-08-26 12:10:00+00'),
(5, 5, 'Delhivery', 'DL-55192830', 'delivered', '2026-09-03 09:30:00+00', '2026-09-05 16:00:00+00'),
(6, 6, 'BlueDart Express', 'BD-44192832', 'delivered', '2026-09-06 08:15:00+00', '2026-09-08 11:30:00+00'),
(7, 7, 'Delhivery', 'DL-33192841', 'in_transit', '2026-09-09 10:00:00+00', NULL),
(8, 9, 'BlueDart Express', 'BD-22192840', 'delivered', '2026-09-15 08:00:00+00', '2026-09-17 14:00:00+00')
ON CONFLICT (id) DO NOTHING;

SELECT setval('demo.shipments_id_seq', (SELECT MAX(id) FROM demo.shipments));

-- Reviews
INSERT INTO demo.reviews (id, product_id, customer_id, rating, title, comment, created_at) VALUES
(1, 1, 1, 5, 'Unbelievable sound clarity and ANC', 'ANC blocks all AC and traffic noise. Battery lasts over 30 hours easily.', '2026-08-15 14:20:00+00'),
(2, 2, 1, 4, 'Great tactile feedback', 'Sturdy build and responsive switches. Software could be a bit cleaner.', '2026-08-18 19:10:00+00'),
(3, 1, 2, 5, 'Best headphones in this price range', 'Bought two pairs, one for work and one for home. Extremely comfortable.', '2026-08-24 11:05:00+00'),
(4, 6, 2, 4, 'Comfortable for long runs', 'Lightweight with great cushioning. True to size.', '2026-08-28 16:40:00+00'),
(5, 9, 3, 5, 'Superior heat distribution', 'Nothing sticks when properly preheated. Restaurant quality sear.', '2026-08-30 08:15:00+00'),
(6, 8, 4, 5, 'Elegant aesthetic and smooth brew', 'Looks gorgeous on the counter and brews a clean cup of coffee.', '2026-09-07 10:30:00+00'),
(7, 1, 5, 5, 'Worth every rupee', 'Switched from a much more expensive brand and could not be happier.', '2026-09-10 17:50:00+00'),
(8, 9, 7, 5, 'Durable and heavy duty', 'Feels like it will last a lifetime. Cleans up effortlessly.', '2026-09-18 12:00:00+00')
ON CONFLICT (id) DO NOTHING;

SELECT setval('demo.reviews_id_seq', (SELECT MAX(id) FROM demo.reviews));
