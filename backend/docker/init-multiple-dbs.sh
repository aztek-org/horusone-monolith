#!/bin/bash
# ============================================================================
# init-multiple-dbs.sh
# Creates additional databases required by the Horus stack.
# This script runs automatically on FIRST postgres start only, via the
# /docker-entrypoint-initdb.d/ mechanism.
#
# Databases created:
#   - horus_db      (already created by POSTGRES_DB env var)
#   - keycloak_db   (for Keycloak identity provider)
# ============================================================================
set -e
set -u

echo "==> Creating keycloak database and user..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create a dedicated keycloak user
    CREATE USER keycloak WITH PASSWORD 'keycloak';

    -- Create the keycloak database owned by the keycloak user
    CREATE DATABASE keycloak_db OWNER keycloak;
EOSQL

# Grant schema-level permissions (required for PostgreSQL 15+)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "keycloak_db" <<-EOSQL
    GRANT ALL ON SCHEMA public TO keycloak;
EOSQL

echo "==> Keycloak database and user created successfully."
