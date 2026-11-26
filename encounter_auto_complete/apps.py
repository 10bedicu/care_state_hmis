from django.apps import AppConfig

PLUGIN_NAME = "encounter_auto_complete"


class EncounterAutoCompleteConfig(AppConfig):
    name = PLUGIN_NAME

    def ready(self):
        from encounter_auto_complete.settings import get_class_time_limits

        get_class_time_limits()
