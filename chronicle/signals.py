from django.core.signals import Signal


revision_complete = Signal(providing_args=['revision'])
