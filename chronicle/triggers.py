from django.db import connection
from django.apps import apps
from django.conf import settings

from .models import HistoryMixin


def escape_identifier(s):
    return '"%s"' % s.replace('"', '\"')

def escape_trigger_name(s):
    # FIXME implement
    return s

def escape_function_name(s):
    # FIXME implement
    return s

# FIXME
# The following triggers only insert values in the *_history tables. If the
# code executes Model.objects.update(...) or obj.save(update_fields=(...))
# without 'revision' in the `update_fields` it will not set the revision
# correctly. The triggers need to be changed so that the revision_id is
# also set in the original INSERT/UPDATE query.

INSERT_UPDATE_FUNCTION_SQL = '''CREATE FUNCTION %(function_name)s() RETURNS trigger AS
$BODY$
BEGIN
    INSERT INTO %(history_table)s (%(fields)s, "revision_id", "_op") VALUES (%(values)s, current_setting('chronicle.revision_id')::%(revision_id_type)s, TG_OP)
    ON CONFLICT ON CONSTRAINT %(unique_together_constraint)s DO UPDATE SET %(update_set)s;
    RETURN NEW;
END
$BODY$
LANGUAGE plpgsql VOLATILE
COST 100;
'''

INSERT_UPDATE_TRIGGER_SQL = '''CREATE TRIGGER %(trigger_name)s
AFTER INSERT OR UPDATE
ON %(table)s
FOR EACH ROW
EXECUTE PROCEDURE %(function_name)s();
'''

DELETE_FUNCTION_SQL = '''CREATE FUNCTION %(function_name)s() RETURNS trigger AS
$BODY$
BEGIN
    DELETE FROM %(history_table)s WHERE "id"=OLD."id" AND "revision_id"=current_setting('chronicle.revision_id')::%(revision_id_type)s;
    INSERT INTO %(history_table)s (%(fields)s, "revision_id", "_op") VALUES (%(values)s, current_setting('chronicle.revision_id')::$(revision_id_type)s, TG_OP);
    RETURN OLD;
END
$BODY$
LANGUAGE plpgsql VOLATILE
COST 100;
'''

DELETE_TRIGGER_SQL = '''CREATE TRIGGER %(trigger_name)s
BEFORE DELETE
ON %(table)s
FOR EACH ROW
EXECUTE PROCEDURE %(function_name)s();
'''

def get_unique_together_constraint(model, cursor):
    # Get name of unique_together constraint. There is no currently no better way
    # than accessing the system tables and get the only *_uniq constraint from there.
    cursor.execute('SELECT "conname" FROM "pg_constraint" WHERE "conrelid"=(SELECT "oid" FROM "pg_class" WHERE "relname" LIKE %s)', (model.History._meta.db_table,))
    constraints = cursor.fetchall()
    constraints = [c[0] for c in constraints if c[0].endswith('_uniq')]
    if len(constraints) != 1:
        raise RuntimeError('Could not autodetect unique_together constraint. More than one constraint ending with _uniq was found: %s' % (', '.join(constraints)))
    return constraints[0]

def create_trigger(model, cursor):
    unique_together_constraint = get_unique_together_constraint(model, cursor)
    fields = [
        field.db_column or field.get_attname()
        for field in model._meta.local_fields
        if field.name != 'revision'
    ]
    d = {
        'trigger_name': escape_trigger_name('chronicle_%s_save_trigger' % model._meta.db_table),
        'function_name': escape_function_name('chronicle_%s_insert_save_history' % model._meta.db_table),
        'table': model._meta.db_table,
        'history_table': model.History._meta.db_table,
        'fields': ', '.join(escape_identifier(f) for f in fields),
        'values': ', '.join('NEW.' + escape_identifier(f) for f in fields),
        'update_set': ', '.join('%s=%s' % (escape_identifier(f), 'NEW.' + escape_identifier(f)) for f in fields),
        'unique_together_constraint': unique_together_constraint,
        'revision_id_type': getattr(settings, 'REVISION_ID_TYPE', 'int'),
    }
    cursor.execute(INSERT_UPDATE_FUNCTION_SQL % d)
    cursor.execute(INSERT_UPDATE_TRIGGER_SQL % d)
    d = {
        'trigger_name': escape_trigger_name('chronicle_%s_delete_trigger' % model._meta.db_table),
        'function_name': escape_function_name('chronicle_%s_insert_delete_history' % model._meta.db_table),
        'session_variable_name': 'chronicle.revision_id',
        'table': model._meta.db_table,
        'history_table': model.History._meta.db_table,
        'fields': ', '.join(escape_identifier(f) for f in fields),
        'values': ', '.join('OLD.' + escape_identifier(f) for f in fields),
        'revision_id_type': getattr(settings, 'REVISION_ID_TYPE', 'int'),
    }
    cursor.execute(DELETE_FUNCTION_SQL % d)
    cursor.execute(DELETE_TRIGGER_SQL % d)


def recreate():
    with connection.cursor() as cursor:
        print 'Dropping existing chronicle_* triggers:'
        cursor.execute("SELECT relname, tgname FROM pg_trigger JOIN pg_class ON tgrelid=pg_class.oid WHERE tgname LIKE 'chronicle_%'")
        triggers = list(cursor.fetchall())
        for trigger in triggers:
            print('- %s.%s' % trigger)
            cursor.execute("DROP TRIGGER %s ON %s" % (
                    escape_identifier(trigger[1]),
                    escape_identifier(trigger[0])))
        print('Dropping existing chronicle_* functions:')
        cursor.execute("SELECT proname FROM pg_proc WHERE proname LIKE 'chronicle_%'")
        names = [row[0] for row in cursor.fetchall()]
        for name in names:
            print('- %s' % name)
            cursor.execute("DROP FUNCTION %s();" % escape_identifier(name))
        print('Creating new chronicle_* triggers:')
        for model in apps.get_models():
            if issubclass(model, HistoryMixin):
                print('- %s.%s' % (model._meta.app_label, model._meta.model_name))
                create_trigger(model, cursor)
