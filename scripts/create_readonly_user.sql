-- scripts/create_readonly_user.sql
-- Create read-only database user for Python AI Service
-- Run this as postgres superuser:
--   psql -U postgres -d idempiere -f scripts/create_readonly_user.sql

-- Create the read-only user
DO $$
BEGIN
    -- Create user if not exists
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ai_readonly') THEN
        CREATE ROLE ai_readonly WITH LOGIN PASSWORD 'change-me-in-production';
        RAISE NOTICE 'Created user ai_readonly';
    ELSE
        RAISE NOTICE 'User ai_readonly already exists';
    END IF;
END
$$;

-- Grant connect permissions
GRANT CONNECT ON DATABASE idempiere TO ai_readonly;

-- Grant usage on adempiere schema
GRANT USAGE ON SCHEMA adempiere TO ai_readonly;

-- Grant SELECT on all tables in adempiere schema
GRANT SELECT ON ALL TABLES IN SCHEMA adempiere TO ai_readonly;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA adempiere GRANT SELECT ON TABLES TO ai_readonly;

-- Set statement timeout to 10 seconds (prevents long-running queries)
ALTER ROLE ai_readonly SET statement_timeout = '10s';

-- Set search_path to adempiere (so queries don't need schema prefix)
ALTER ROLE ai_readonly SET search_path = adempiere;

-- Revoke all write permissions
REVOKE CREATE ON SCHEMA adempiere FROM ai_readonly;
REVOKE ALL ON DATABASE idempiere FROM ai_readonly;

-- Verify permissions
\echo '=== Permissions for ai_readonly ==='
\du ai_readonly
