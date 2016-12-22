from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.transaction import atomic


def escape_identifier(s):
    return '"%s"' % s.replace('"', '\"')


INSERT_SQL = 'INSERT INTO %(history_table)s (%(fields)s, "revision_id", "_op") SELECT %(fields)s, %%s, \'INSERT\' FROM %(table)s'


class Command(BaseCommand):

    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument('--truncate', action='store_true', default=False)

    @atomic
    def handle(self, *args, **options):
        from chronicle import get_models_with_history
        Revision = apps.get_model(settings.REVISION_MODEL)
        if options['truncate']:
            for model in get_models_with_history():
                model.objects.update(revision=None)
                model.History.objects.delete()
            Revision.objects.delete()
        if Revision.objects.exists():
            raise CommandError("A revision already exists.")
        revision = Revision.objects.create()
        with connection.cursor() as cursor:
            for model in get_models_with_history():
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
                sql = INSERT_SQL % d
                cursor.execute(sql, (revision.id,))
