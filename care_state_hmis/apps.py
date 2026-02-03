from django.apps import AppConfig

PLUGIN_NAME = "care_state_hmis"


class CareSSMMConfig(AppConfig):
    name = PLUGIN_NAME

    def ready(self):
        import care_state_hmis.signals  # noqa
