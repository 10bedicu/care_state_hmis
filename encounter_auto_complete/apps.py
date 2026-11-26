from django.apps import AppConfig


class EncounterAutoCompleteConfig(AppConfig):
    name = "encounter_auto_complete"

    def ready(self):
        from encounter_auto_complete.settings import get_encounter_classes

        get_encounter_classes()
