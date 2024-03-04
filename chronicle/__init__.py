import threading

from django.db import connection

local = threading.local()


def get_current_revision(allow_none=False):
    if not allow_none and not getattr(local, 'revision', None):
        raise RuntimeError('No active revision')
    return getattr(local, 'revision', None)


def set_current_revision(revision, database=True):
    local.revision = revision
    if database:
        with connection.cursor() as cursor:
            # The idea to use a non-standard session variable was taken from
            # the following StackOverflow article:
            # http://stackoverflow.com/a/19410907/994342
            if revision:
                cursor.execute("SELECT set_config('chronicle.revision_id', %s::varchar, true)", [revision.id])
            else:
                cursor.execute("SELECT set_config('chronicle.revision_id', '', true)")


def get_models_with_history():
    from django.apps import apps
    # FIXME this should be cached
    from .models import HistoryMixin
    return [
        model for model in apps.get_models()
        if issubclass(model, HistoryMixin)
    ]
