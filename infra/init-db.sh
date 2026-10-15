#!/bin/sh
set -e
# Creates 3 logical DBs on single Postgres for local dev.
# In prod each service gets its own instance — isolation is logical here.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
  SELECT 'CREATE DATABASE auth_db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'auth_db')\gexec
  SELECT 'CREATE DATABASE shop_db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'shop_db')\gexec
  SELECT 'CREATE DATABASE billing_db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'billing_db')\gexec
EOSQL
