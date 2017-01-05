from __future__ import print_function

from django.apps import apps as global_apps
from django.conf import settings
from django.db import connection

from .models import HistoryMixin


INSERT_HISTORY_SQL = 'INSERT INTO %(history_table)s (%(fields)s, "revision_id", "_op") SELECT %(fields)s, %%s, \'INSERT\' FROM %(table)s WHERE revision_id IS NULL'


def escape_identifier(s):
    return '"%s"' % s.replace('"', '\"')


def create_initial_history(apps=global_apps):
    models = [
        model for model in apps.get_models()
        if issubclass(model, HistoryMixin)
    ]
    # Check if there are actually any objects without an revision
    for model in models:
        if model.objects.filter(revision=None).exists():
            break
    else:
        # No model without a revision found. Abort.
        return
    Revision = apps.get_model(settings.REVISION_MODEL)
    revision = Revision.objects.create()
    print('Creating initial history:')
    with connection.cursor() as cursor:
        for model in models:
            print('- %s.%s (%d)' % (model._meta.app_label, model._meta.model_name, model.objects.filter(revision=None).count()))
            fields = [
                field.db_column or field.get_attname()
                for field in model._meta.local_fields
                if field.name != 'revision'
            ]
            d = {
                'table': model._meta.db_table,
                'history_table': model.History._meta.db_table,
                'fields': ', '.join(escape_identifier(f) for f in fields),
            }
            sql = INSERT_HISTORY_SQL % d
            cursor.execute(sql, (revision.id,))
        for model in models:
            model.objects.filter(revision=None).update(revision=revision)
