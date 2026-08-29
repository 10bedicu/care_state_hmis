from django.apps import AppConfig

PLUGIN_NAME = "appointment_revisit_charge"


class AppointmentRevisitChargeConfig(AppConfig):
    name = PLUGIN_NAME

    def ready(self):
        import appointment_revisit_charge.signals  # noqa
