"""Actual driver/role/slot checks against an explicitly disposable fixture DB."""
import importlib.metadata
import json
from pathlib import Path
import secrets
import sys

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'services/fegcraft-assistant'))
from runtime import local_slot, SLOT

ROLE = 'vector_fegcraft_slot'
SCHEMA = 'vector_admission_fixture'


def check(value, code):
    if not value:
        raise RuntimeError(code)


def qualify(config):
    # This flag/database name is a deliberate refusal boundary. This program
    # must NEVER receive the production Vector database or its credentials.
    check(set(config) == {'disposable', 'dsn'} and config['disposable'] is True, 'DISPOSABLE_DATABASE_REQUIRED')
    options = conninfo_to_dict(config['dsn'])
    check(options.get('dbname') == 'vector_admission_fixture', 'FIXTURE_DATABASE_NAME_REQUIRED')
    check(importlib.metadata.version('psycopg') == '3.2.13' and psycopg.pq.__impl__ == 'binary', 'BINARY_DRIVER_PIN_MISMATCH')
    password = secrets.token_hex(32)
    role_dsn = make_conninfo(config['dsn'], user=ROLE, password=password)
    created_role = created_schema = False
    with psycopg.connect(config['dsn'], autocommit=True, connect_timeout=3) as admin:
        try:
            check(not admin.execute('SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=%s)', (ROLE,)).fetchone()[0], 'FIXTURE_ROLE_ALREADY_EXISTS')
            check(not admin.execute('SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname=%s)', (SCHEMA,)).fetchone()[0], 'FIXTURE_SCHEMA_ALREADY_EXISTS')
            admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 2 PASSWORD {}').format(sql.Identifier(ROLE), sql.Literal(password)))
            created_role = True
            for key, value in [('statement_timeout','3s'), ('lock_timeout','1s'), ('idle_in_transaction_session_timeout','5s'),
                               ('idle_session_timeout','45s'), ('default_transaction_read_only','on'), ('search_path','pg_catalog')]:
                admin.execute(sql.SQL('ALTER ROLE {} SET {} TO {}').format(sql.Identifier(ROLE), sql.Identifier(key), sql.Literal(value)))
            admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(SCHEMA)))
            created_schema = True
            admin.execute(sql.SQL('CREATE TABLE {}.private_fixture(value text)').format(sql.Identifier(SCHEMA)))
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(sql.Identifier(SCHEMA), sql.Identifier(ROLE)))
            with psycopg.connect(role_dsn, autocommit=True, connect_timeout=3) as role:
                check(role.execute('SELECT current_user').fetchone()[0] == ROLE, 'ROLE_IDENTITY_MISMATCH')
                check(role.execute('SHOW default_transaction_read_only').fetchone()[0] == 'on', 'READ_ONLY_DEFAULT_MISSING')
                # This default is an accident guard, NOT an unchangeable security
                # boundary. Test hard privileges after the role turns it off.
                role.execute('SET default_transaction_read_only=off')
                for statement in (sql.SQL('SELECT * FROM {}.private_fixture').format(sql.Identifier(SCHEMA)),
                                  sql.SQL('CREATE TABLE {}.denied(value int)').format(sql.Identifier(SCHEMA)),
                                  sql.SQL('CREATE TABLE public.vector_admission_denied(value int)'),
                                  sql.SQL('CREATE SCHEMA vector_admission_denied')):
                    try:
                        role.execute(statement)
                    except psycopg.errors.InsufficientPrivilege:
                        pass
                    else:
                        raise RuntimeError('UNEXPECTED_APPLICATION_OR_CREATE_PRIVILEGE')
                inherited_temp = role.execute("SELECT has_database_privilege(current_user,current_database(),'TEMP')").fetchone()[0]
                check(inherited_temp is True, 'PUBLIC_TEMP_FIXTURE_DIFFERS')
                role.execute('CREATE TEMP TABLE vector_admission_temporary(value int)')
                role.execute('DROP TABLE vector_admission_temporary')
            attributes = admin.execute('SELECT rolsuper,rolcreatedb,rolcreaterole,rolinherit,rolreplication,rolbypassrls,rolconnlimit FROM pg_roles WHERE rolname=%s',(ROLE,)).fetchone()
            check(attributes == (False,False,False,False,False,False,2), 'ROLE_ATTRIBUTES_MISMATCH')
            check(admin.execute('SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=%s)',(ROLE,)).fetchone()[0] == 0, 'ROLE_MEMBERSHIP_MISMATCH')
            check(admin.execute('SELECT pg_try_advisory_lock(%s::bigint)',(SLOT,)).fetchone()[0], 'FIXTURE_SLOT_NOT_AVAILABLE')
            try:
                try:
                    with local_slot(role_dsn):
                        raise RuntimeError('CONTENTION_WAS_NOT_BLOCKED')
                except RuntimeError as exc:
                    check(str(exc) == 'LOCAL_BUSY', 'CONTENTION_CONTRACT_MISMATCH')
            finally:
                admin.execute('SELECT pg_advisory_unlock(%s::bigint)',(SLOT,))
            with local_slot(role_dsn):
                check(admin.execute('SELECT pg_try_advisory_lock(%s::bigint)',(SLOT,)).fetchone()[0] is False, 'REVERSE_CONTENTION_FAILED')
            check(admin.execute('SELECT pg_try_advisory_lock(%s::bigint)',(SLOT,)).fetchone()[0], 'NORMAL_RELEASE_FAILED')
            admin.execute('SELECT pg_advisory_unlock(%s::bigint)',(SLOT,))
            try:
                with local_slot(role_dsn):
                    raise ValueError('synthetic-failure')
            except ValueError:
                pass
            check(admin.execute('SELECT pg_try_advisory_lock(%s::bigint)',(SLOT,)).fetchone()[0], 'EXCEPTION_RELEASE_FAILED')
            admin.execute('SELECT pg_advisory_unlock(%s::bigint)',(SLOT,))
            version = admin.execute('SHOW server_version_num').fetchone()[0]
        finally:
            if created_schema:
                admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(SCHEMA)))
            if created_role:
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(ROLE)))
    return {'passed':True,'driver_version':'3.2.13','binary':True,'server_version_num':int(version),
      'disposable_database':True,'permanent_create_denied':True,'application_read_denied':True,
      'inherited_public_temp':True,'temporary_table_creation_possible':True,'global_public_acl_changed':False,
      'contention_both_directions_passed':True,'normal_and_exception_release_passed':True,
      'fixture_role_and_schema_removed':True,'production_role_created':False,'model_calls':0,'cloud_calls':0}


if __name__ == '__main__':
    try:
        result = qualify(json.loads(Path(sys.argv[1]).read_text()))
        print(json.dumps(result))
    except Exception as exc:
        # Driver exceptions can contain connection details; print only a class
        # or our fixed uppercase failure code, never the raw psycopg exception.
        print(json.dumps({'passed':False,'error':str(exc) if type(exc) is RuntimeError else type(exc).__name__}))
        raise SystemExit(1)
