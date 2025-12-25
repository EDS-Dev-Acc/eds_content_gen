-- EMCIP Database Initialization Script
-- This script runs when Postgres container is first created

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- Grant privileges (if using different user)
-- GRANT ALL PRIVILEGES ON DATABASE emcip TO emcip;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'EMCIP database initialized successfully';
END $$;
