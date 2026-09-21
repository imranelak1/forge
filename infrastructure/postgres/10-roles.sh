#!/usr/bin/env bash
set -euo pipefail

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set ON_ERROR_STOP=1 <<'SQL'
\getenv app_password FORGE_DATABASE_PASSWORD
\getenv migration_password FORGE_MIGRATION_PASSWORD
SELECT format('CREATE ROLE forge_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'forge_app') \gexec
SELECT format('CREATE ROLE forge_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD %L', :'migration_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'forge_migrator') \gexec
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database()) \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO forge_app, forge_migrator', current_database()) \gexec
SELECT format('GRANT CREATE ON DATABASE %I TO forge_migrator', current_database()) \gexec
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO forge_app, forge_migrator;
GRANT CREATE ON SCHEMA public TO forge_migrator;
ALTER DEFAULT PRIVILEGES FOR ROLE forge_migrator IN SCHEMA public GRANT SELECT ON TABLES TO forge_app;
SQL
