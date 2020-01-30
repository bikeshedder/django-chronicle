from __future__ import print_function
from __future__ import unicode_literals

import sys

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
    revision = models.ForeignKey(settings.REVISION_MODEL, null=True, blank=True,
            related_name='+', on_delete=models.SET_NULL)
    history = HistoryManager()

    class Meta:
        abstract = True


class ManyToManyModel(HistoryMixin, models.Model):

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
        unique_together = (('id', 'revision_id'),)
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
        if field.remote_field:
            # Field.remote_field returns an AutoField even if the target
            # field is actually something else. Therefore we use the target
            # field instead.
            field_name = field.name + '_id'
            if isinstance(field.remote_field.model, str):
                # This happens when processing a ForeignKey field which did
                # not resolved because the target app is missing from INSTALLED_APPS.
                # There is nothing we can to about this right now and we just
                # ignore this field as it is already reported by the Django check
                # subsystem.
                continue
            field_cls = type(field.remote_field.get_related_field())
        else:
            field_name = field.name
            field_cls = type(field)
        if issubclass(field_cls, models.AutoField):
            field_cls = models.IntegerField
        if issubclass(field_cls, models.BooleanField):
            field_cls = models.NullBooleanField
        field_kwargs = {
            'null': True,
            'db_column': field.db_column or field.get_attname(),
        }
        COPY_FIELD_KWARGS = ['max_length', 'decimal_places', 'max_digits', 'base_field']
        for kwarg in COPY_FIELD_KWARGS:
            if hasattr(field, kwarg):
                field_kwargs[kwarg] = getattr(field, kwarg)
        attrs[field_name] = field_cls(**field_kwargs)
    history_model = type(model.__name__ + 'History', (History, models.Model), attrs)
    model.History = history_model
    return history_model


class AbstractRevision(models.Model):

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        self._atomic = None
        super(AbstractRevision, self).__init__(*args, **kwargs)

    def __enter__(self):
        if get_current_revision(allow_none=True):
            raise RuntimeError('Another revision is already active')
        self._atomic = atomic()
        self._atomic.__enter__()
        try:
            self.save()
            set_current_revision(self)
            return self
        except:
            self._atomic.__exit__(*sys.exc_info())
            self._atomic = None
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            # TODO Is there a good way to detect if the DB connection is still
            # useable? Right now we simply skip the DB operation if the context
            # is exited because of an exception.
            set_current_revision(None, database=not exc_type)
            self._atomic.__exit__(exc_type, exc_value, traceback)
            self._atomic = None
        except:
            self._atomic.__exit__(*sys.exc_info())
            self._atomic = None
            raise
        else:
            revision_complete.send(sender=self.__class__, revision=self)


@receiver(signals.pre_save)
@receiver(signals.pre_delete)
def model_pre_save(sender, instance, raw=False, **options):
    if raw:
        return
    if isinstance(instance, HistoryMixin):
        # Be nice and set the revision field in the pre_save signal. It is
        # also set using the DB trigger so this is not really neccesary.
        instance.revision = get_current_revision()
