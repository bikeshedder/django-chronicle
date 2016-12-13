from __future__ import print_function
from __future__ import unicode_literals

from collections import defaultdict

from django.conf import settings
from django.db import models
from django.db.transaction import atomic

from django.db.models import signals
from django.dispatch import receiver

from . import set_current_revision
from . import get_current_revision
from .signals import revision_complete


class HistoryManager(object):
    pass


class HistoryMixin(models.Model):
    revision = models.ForeignKey(settings.REVISION_MODEL, null=True, blank=True)
    history = HistoryManager()

    class Meta:
        abstract = True


class History(models.Model):
    _op = models.CharField(max_length=10, choices=(
        ('INSERT', 'INSERT'),
        ('UPDATE', 'UPDATE'),
        ('DELETE', 'DELETE'),
        ('TRUNCATE', 'TRUNCATE'),
    ))
    class Meta:
        abstract = True


class HistoryField(models.Field):

    def __init__(self, original_field):
        self.original_field

    def db_type(self, connection):
        return self.original_field.db_type(connection)


def create_history_model(model):
    class Meta:
        db_table = model._meta.db_table + '_history'
        #unique_together = (('id', 'revision'),)
    attrs = {
        '__module__': model.__module__,
        # The _pk column is just here to make django happy. Django requires
        # all DB objects to have a primary_key field.
        '_pk': models.AutoField(primary_key=True),
        'Meta': Meta
    }
    for field in model._meta.local_fields:
        # XXX should we use a proper revision FK field? right now it is reduced
        # to a single integer
        if field.rel:
            # Field.remote_field returns an AutoField even if the target
            # field is actually something else. Therefore we use the
            # Meta.get_field() method from the target model.
            field_cls = type(field.remote_field.to._meta.get_field(
                    field.remote_field.target_field.name))
        else:
            field_cls = type(field)
        if issubclass(field_cls, models.AutoField):
            field_cls = models.IntegerField
        if issubclass(field_cls, models.BooleanField):
            field_cls = models.NullBooleanField
        field_kwargs = {
            'null': True,
            'db_column': field.db_column or field.get_attname(),
        }
        COPY_FIELD_KWARGS = ['max_length', 'decimal_places', 'max_digits']
        for kwarg in COPY_FIELD_KWARGS:
            if hasattr(field, kwarg):
                field_kwargs[kwarg] = getattr(field, kwarg)
        attrs[field.name] = field_cls(**field_kwargs)
    #print(set(field.name for field in model._meta.get_fields() if field.concrete) - \
    #        set(field.name for field in model._meta.local_fields))
    history_model = type(model.__name__ + b'History', (History, models.Model), attrs)
    model.History = history_model
    return history_model


class AbstractRevision(models.Model):

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        self.objects_created = defaultdict(lambda: [])
        self.objects_updated = defaultdict(lambda: [])
        self.objects_deleted = defaultdict(lambda: [])
        self._atomic = None
        super(AbstractRevision, self).__init__(*args, **kwargs)

    def __enter__(self):
        if get_current_revision(allow_none=True):
            raise RuntimeError('Another revision is already active')
        self._atomic = atomic()
        self._atomic.__enter__()
        self.save()
        set_current_revision(self)

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                revision_complete.send(sender=self)
            self._atomic.__exit__(exc_type, exc_value, traceback)
        finally:
            set_current_revision(None)
            self._atomic = None

    def add_created(self, obj):
        self.objects_created[obj.__class__].append(obj)

    def add_updated(self, obj):
        self.objects_updated[obj.__class__].append(obj)

    def add_deleted(self, obj):
        self.objects_deleted[obj.__class__].append(obj)


@receiver(signals.pre_save)
def model_pre_save(sender, instance, raw, update_fields=None, **options):
    if raw:
        return
    if isinstance(instance, HistoryMixin):
        # Be nice and set the revision field in the pre_save signal. It is
        # also set using the DB trigger so this is not really neccesary.
        instance.revision = get_current_revision()
        if instance.id:
            instance.revision.add_updated(instance)
        else:
            instance.revision.add_created(instance)
