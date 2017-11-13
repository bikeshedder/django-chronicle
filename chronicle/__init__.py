import threading

from django.apps import AppConfig
from django.apps import apps
from django.db import connection
from django.db.models import signals
from django.dispatch import receiver

__version__ = '0.1.0'


local = threading.local()


def on_pre_migrate(**kwargs):
    from . import triggers
    triggers.drop_triggers()


def on_post_migrate(**kwargs):
    from . import utils
    utils.create_initial_history()
    from . import triggers
    triggers.create_triggers()


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
    # FIXME this should be cached
    from .models import HistoryMixin
    return [
        model for model in apps.get_models()
        if issubclass(model, HistoryMixin)
    ]


class ChronicleAppConfig(AppConfig):
    name = 'chronicle'
    verbose_name = 'Chronicle'

    def __init__(self, *args, **kwargs):
        super(ChronicleAppConfig, self).__init__(*args, **kwargs)
        #signals.class_prepared.connect(on_class_prepared)
        signals.pre_migrate.connect(on_pre_migrate, sender=self)
        signals.post_migrate.connect(on_post_migrate, sender=self)

    def ready(self):
        from .models import create_history_model
        for model in get_models_with_history():
            create_history_model(model)


default_app_config = 'chronicle.ChronicleAppConfig'
