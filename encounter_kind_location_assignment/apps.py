from django.apps import AppConfig

PLUGIN_NAME = "encounter_kind_location_assignment"


class PatientDemographicsConfig(AppConfig):
    name = PLUGIN_NAME

    def ready(self):
        """
        Import models, signals, and other dependencies here to ensure
        Django's app registry is fully initialized before use.
        """

        import encounter_kind_location_assignment.extensions  # noqa
