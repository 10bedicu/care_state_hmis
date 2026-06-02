from django.apps import AppConfig

PLUGIN_NAME = "encounter_attender"


class EncounterAttenderConfig(AppConfig):
    name = PLUGIN_NAME

    def ready(self):
        import encounter_attender.extensions
