from django.apps import AppConfig

PLUGIN_NAME = "care_state_hmis"


class CareSSMMConfig(AppConfig):
    name = PLUGIN_NAME

    def ready(self):
        import encounter_identifiers.signals  # noqa
        import care_state_hmis.signals  # noqa
        import care_state_hmis.authorization  # noqa
        import care_state_hmis.extensions  # noqa
