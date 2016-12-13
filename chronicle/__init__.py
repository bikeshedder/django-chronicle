import threading

from django.apps import AppConfig
from django.apps import apps
from django.db import connection
from django.db.models import signals

__version__ == '0.1.0'


local = threading.local()


def get_current_revision(allow_none=False):
    if not allow_none and not getattr(local, 'revision', None):
        raise RuntimeError('No active revision')
    return getattr(local, 'revision', None)


def set_current_revision(revision):
    local.revision = revision
    with connection.cursor() as cursor:
        # The idea to use a non-standard session variable was taken from
        # the following StackOverflow article:
        # http://stackoverflow.com/a/19410907/994342
        if revision:
            cursor.execute('SET chronicle.revision_id = %s', [revision.id])
        else:
            cursor.execute('SET chronicle.revision_id TO DEFAULT')


class ChronicleAppConfig(AppConfig):
    name = 'chronicle'
    verbose_name = 'Chronicle'

    def __init__(self, *args, **kwargs):
        super(ChronicleAppConfig, self).__init__(*args, **kwargs)
        #signals.class_prepared.connect(on_class_prepared)

    def ready(self):
        from .models import create_history_model
        from .models import HistoryMixin
        for model in apps.get_models():
            if issubclass(model, HistoryMixin):
                create_history_model(model)


default_app_config = 'chronicle.ChronicleAppConfig'
