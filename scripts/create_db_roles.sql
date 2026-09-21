-- ScribeQL Database, Schemas, and Role Configuration
-- Dialect: PostgreSQL

-- Note: Execute as superuser (postgres)

-- 1. Create database if it does not exist (run in postgres db or maintenance db)
-- CREATE DATABASE scribeql;

-- Connect to database scribeql before running the below commands:
-- \c scribeql

-- 2. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 3. Create schemas
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS demo;

-- 4. Create roles
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_rw') THEN
        CREATE ROLE app_rw WITH LOGIN PASSWORD 'app_rw_password_dev';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'sql_ro') THEN
        CREATE ROLE sql_ro WITH LOGIN PASSWORD 'sql_ro_password_dev';
    END IF;
END $$;

-- 5. Privileges for app_rw (Application Read/Write)
GRANT CONNECT ON DATABASE scribeql TO app_rw;
GRANT USAGE, CREATE ON SCHEMA app TO app_rw;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA app TO app_rw;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA app TO app_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT ALL PRIVILEGES ON TABLES TO app_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT ALL PRIVILEGES ON SEQUENCES TO app_rw;

GRANT USAGE, CREATE ON SCHEMA demo TO app_rw;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA demo TO app_rw;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA demo TO app_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA demo GRANT ALL PRIVILEGES ON TABLES TO app_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA demo GRANT ALL PRIVILEGES ON SEQUENCES TO app_rw;

-- 6. Privileges for sql_ro (Demo Execution Boundary: Read-Only on demo, NO access to app)
GRANT CONNECT ON DATABASE scribeql TO sql_ro;

-- Strictly deny access to app schema and public schema
REVOKE ALL ON SCHEMA app FROM sql_ro;
REVOKE ALL ON ALL TABLES IN SCHEMA app FROM sql_ro;
REVOKE ALL ON SCHEMA public FROM sql_ro;

-- Allow SELECT on demo schema only
GRANT USAGE ON SCHEMA demo TO sql_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA demo TO sql_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA demo GRANT SELECT ON TABLES TO sql_ro;

-- Hard resource and security constraints on sql_ro
ALTER ROLE sql_ro SET default_transaction_read_only = on;
ALTER ROLE sql_ro SET statement_timeout = '15s';
ALTER ROLE sql_ro SET lock_timeout = '3s';
ALTER ROLE sql_ro SET search_path = demo;
