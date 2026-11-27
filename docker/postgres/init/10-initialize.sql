CREATE EXTENSION IF NOT EXISTS vector;

DO $$
DECLARE
    app_role name := current_user;
    app_database name := current_database();
BEGIN
    EXECUTE format(
        'GRANT CONNECT, CREATE, TEMPORARY ON DATABASE %I TO %I',
        app_database,
        app_role
    );
    EXECUTE format(
        'GRANT USAGE, CREATE ON SCHEMA public TO %I',
        app_role
    );
    EXECUTE format(
        'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO %I',
        app_role
    );
    EXECUTE format(
        'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO %I',
        app_role
    );
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
        'GRANT ALL PRIVILEGES ON TABLES TO %I',
        app_role,
        app_role
    );
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
        'GRANT ALL PRIVILEGES ON SEQUENCES TO %I',
        app_role,
        app_role
    );
END
$$;
