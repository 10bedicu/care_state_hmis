import environ
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.settings import perform_import

from care.emr.resources.encounter.constants import ClassChoices
from encounter_auto_complete.apps import PLUGIN_NAME

env = environ.Env()


class PluginSettings:  # pragma: no cover
    def __init__(
        self,
        plugin_name: str | None = None,
        defaults: dict | None = None,
        import_strings: set | None = None,
        required_settings: set | None = None,
    ) -> None:
        if not plugin_name:
            raise ValueError("Plugin name must be provided")
        self.plugin_name = plugin_name
        self.defaults = defaults or {}
        self.import_strings = import_strings or set()
        self.required_settings = required_settings or set()
        self._cached_attrs = set()

    def __getattr__(self, attr):
        if attr not in self.defaults:
            raise AttributeError("Invalid setting: '%s'" % attr)

        # Try to find the setting from user settings, then from environment variables
        val = self.defaults[attr]
        try:
            val = self.user_settings[attr]
        except KeyError:
            try:
                # Lists and dicts are read as JSON so rules can use named keys.
                val = env.json(attr) if isinstance(val, list | dict) else env(attr, cast=type(val))
            except environ.ImproperlyConfigured:
                # Fall back to defaults
                pass

        # Coerce import strings into classes
        if attr in self.import_strings:
            val = perform_import(val, attr)

        self._cached_attrs.add(attr)
        setattr(self, attr, val)
        return val

    @property
    def user_settings(self) -> dict:
        if not hasattr(self, "_user_settings"):
            self._user_settings = getattr(settings, "PLUGIN_CONFIGS", {}).get(self.plugin_name, {})
        return self._user_settings


REQUIRED_SETTINGS = {}

DEFAULTS = {
    # e.g. [{"encounter_class": "amb"}, {"encounter_class": "obsenc", "time_limit_hours": 24}]
    "ENCOUNTER_AUTO_COMPLETE_RULES": [],
}

plugin_settings = PluginSettings(PLUGIN_NAME, defaults=DEFAULTS, required_settings=REQUIRED_SETTINGS)

RULE_KEYS = {"encounter_class", "time_limit_hours"}
ENCOUNTER_CLASSES = {choice.value for choice in ClassChoices}


def get_class_time_limits():
    """Return {encounter_class: time limit in hours}; no rules disables completion."""
    try:
        rules = plugin_settings.ENCOUNTER_AUTO_COMPLETE_RULES
    except ValueError as e:
        raise ImproperlyConfigured("ENCOUNTER_AUTO_COMPLETE_RULES is not valid JSON") from e
    if not isinstance(rules, list):
        raise ImproperlyConfigured("ENCOUNTER_AUTO_COMPLETE_RULES must be a list of rules")

    limits = {}
    for rule in rules:
        # Unknown keys are rejected so a typo cannot silently drop a time limit.
        if not isinstance(rule, dict) or set(rule) - RULE_KEYS:
            raise ImproperlyConfigured(f"Invalid ENCOUNTER_AUTO_COMPLETE_RULES rule: {rule!r}")
        encounter_class = rule.get("encounter_class")
        hours = rule.get("time_limit_hours", 0)
        if encounter_class not in ENCOUNTER_CLASSES or type(hours) is not int or hours < 0:
            raise ImproperlyConfigured(f"Invalid ENCOUNTER_AUTO_COMPLETE_RULES rule: {rule!r}")
        if encounter_class in limits:
            raise ImproperlyConfigured(f"Duplicate ENCOUNTER_AUTO_COMPLETE_RULES rule for {encounter_class!r}")
        limits[encounter_class] = hours
    return limits
