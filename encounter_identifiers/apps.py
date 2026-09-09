from django.apps import AppConfig

PLUGIN_NAME = "encounter_identifiers"


class EncounterIdentifiersConfig(AppConfig):
    name = PLUGIN_NAME

    def ready(self):
        import encounter_identifiers.signals  # noqa
