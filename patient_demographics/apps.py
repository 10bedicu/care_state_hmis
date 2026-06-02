from django.apps import AppConfig

PLUGIN_NAME = "patient_demographics"


class PatientDemographicsConfig(AppConfig):
    name = PLUGIN_NAME

    def ready(self):
        """
        Import models, signals, and other dependencies here to ensure
        Django's app registry is fully initialized before use.
        """

        import patient_demographics.extensions  # noqa
