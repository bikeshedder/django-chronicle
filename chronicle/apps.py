from django.apps import AppConfig
from django.db.models import signals

from . import get_models_with_history


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


def on_pre_migrate(**kwargs):
    from . import triggers
    triggers.drop_triggers()


def on_post_migrate(**kwargs):
    from . import utils
    utils.create_initial_history()
    from . import triggers
    triggers.create_triggers()