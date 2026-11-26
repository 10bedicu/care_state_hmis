import os

from django.core.exceptions import ImproperlyConfigured

from care.emr.resources.encounter.constants import ClassChoices


def get_encounter_classes():
    classes = tuple(
        dict.fromkeys(
            value.strip()
            for value in os.environ.get("ENCOUNTER_AUTO_COMPLETE_CLASSES", "").split(
                ","
            )
            if value.strip()
        )
    )
    invalid = set(classes) - {choice.value for choice in ClassChoices}
    if invalid:
        raise ImproperlyConfigured(
            "Invalid ENCOUNTER_AUTO_COMPLETE_CLASSES: " + ", ".join(sorted(invalid))
        )
    return classes
