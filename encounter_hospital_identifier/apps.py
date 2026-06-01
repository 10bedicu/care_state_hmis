from django.apps import AppConfig

PLUGIN_NAME = "encounter_hospital_identifier"


class EncounterHospitalIdentifierConfig(AppConfig):
    name = PLUGIN_NAME

    def ready(self):
        """
        Import models, signals, and other dependencies here to ensure
        Django's app registry is fully initialized before use.
        """

        import encounter_hospital_identifier.signals  # noqa
