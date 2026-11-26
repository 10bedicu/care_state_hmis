import os
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from celery import current_app
from celery.exceptions import Retry
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError
from django.test import SimpleTestCase
from model_bakery import baker

from care.emr.api.viewsets.location import close_related_location_from_encounter
from care.emr.models import Encounter
from care.emr.models.device import Device, DeviceEncounterHistory
from care.emr.models.location import FacilityLocation, FacilityLocationEncounter
from care.emr.resources.encounter.constants import StatusChoices
from care.utils.tests.base import CareAPITestBase
from encounter_auto_complete.apps import PLUGIN_NAME
from encounter_auto_complete.settings import (
    DEFAULTS,
    PluginSettings,
    get_class_time_limits,
    plugin_settings,
)
from encounter_auto_complete.tasks import complete_encounters

SETTING = "ENCOUNTER_AUTO_COMPLETE_RULES"
MIDNIGHT = datetime(2026, 11, 26, tzinfo=ZoneInfo("Asia/Kolkata"))
AMB = {"encounter_class": "amb"}
VR = {"encounter_class": "vr"}


def configure(rules):
    return patch.object(plugin_settings, SETTING, rules)


class ConfigurationTests(SimpleTestCase):
    def test_no_rules_disables_completion(self):
        with configure([]):
            self.assertEqual(get_class_time_limits(), {})

    def test_time_limit_defaults_to_zero(self):
        with configure([AMB, {"encounter_class": "obsenc", "time_limit_hours": 24}]):
            self.assertEqual(get_class_time_limits(), {"amb": 0, "obsenc": 24})

    def test_rules_are_read_as_json_from_the_environment(self):
        fresh_settings = PluginSettings(PLUGIN_NAME, defaults=DEFAULTS)
        env = {SETTING: '[{"encounter_class": "vr", "time_limit_hours": 6}]'}
        with (
            patch.dict(os.environ, env),
            patch("encounter_auto_complete.settings.plugin_settings", fresh_settings),
        ):
            self.assertEqual(get_class_time_limits(), {"vr": 6})

    def test_invalid_json_fails_app_startup(self):
        fresh_settings = PluginSettings(PLUGIN_NAME, defaults=DEFAULTS)
        with (
            patch.dict(os.environ, {SETTING: "amb,vr"}),
            patch("encounter_auto_complete.settings.plugin_settings", fresh_settings),
            self.assertRaisesMessage(ImproperlyConfigured, "not valid JSON"),
        ):
            apps.get_app_config("encounter_auto_complete").ready()

    def test_invalid_rules_fail_app_startup(self):
        for rules in (
            AMB,
            ["amb"],
            [{"encounter_class": "invalid"}],
            [{"encounter_class": "amb", "time_limit_hours": -1}],
            [{"encounter_class": "amb", "time_limit_hours": 1.5}],
            [{"encounter_class": "amb", "time_limit_hours": "24"}],
            [{"encounter_class": "amb", "time_limit": 24}],
            [AMB, AMB],
        ):
            with (
                self.subTest(rules=rules),
                configure(rules),
                self.assertRaises(ImproperlyConfigured),
            ):
                apps.get_app_config("encounter_auto_complete").ready()

    def test_task_is_discovered_and_registered_for_midnight(self):
        current_app.loader.import_default_modules()
        current_app.finalize()
        entry = current_app.conf.beat_schedule["auto_complete_encounters_at_midnight"]
        self.assertEqual(entry["task"], complete_encounters.name)
        self.assertEqual(entry["schedule"].hour, {0})
        self.assertEqual(entry["schedule"].minute, {0})


class CompletionTests(CareAPITestBase):
    def setUp(self):
        super().setUp()
        self.config = configure([AMB, VR])
        self.config.start()
        self.addCleanup(self.config.stop)
        self.user = self.create_user()
        self.facility = self.create_facility(user=self.user)
        self.patient = self.create_patient()
        self.organization = self.create_facility_organization(facility=self.facility)

    def make_encounter(self, *, created_at=None, **kwargs):
        data = {
            "encounter_class": "amb",
            "status_history": {"history": []},
            "period": {"start": (MIDNIGHT - timedelta(hours=1)).isoformat()},
            "updated_by": self.user,
        }
        data.update(kwargs)
        encounter = self.create_encounter(
            patient=self.patient,
            facility=self.facility,
            organization=self.organization,
            **data,
        )
        Encounter.objects.filter(pk=encounter.pk).update(
            created_date=created_at or MIDNIGHT - timedelta(hours=2)
        )
        return encounter

    def run_task(self):
        return complete_encounters.run(cutoff=MIDNIGHT.isoformat())

    def test_disabled_task_does_not_query_database(self):
        with configure([]), self.assertNumQueries(0):
            self.assertEqual(self.run_task(), 0)

    def test_only_selected_classes_and_open_statuses_are_completed(self):
        encounters = [
            self.make_encounter(status=status.value) for status in StatusChoices
        ]
        excluded_class = self.make_encounter(encounter_class="imp")
        virtual = self.make_encounter(encounter_class="vr")
        deleted = self.make_encounter(deleted=True)

        self.assertEqual(self.run_task(), 4)

        for encounter in encounters:
            before = encounter.status
            encounter.refresh_from_db()
            expected = (
                "completed"
                if before in {"in_progress", "on_hold", "discharged"}
                else before
            )
            self.assertEqual(encounter.status, expected)
        excluded_class.refresh_from_db()
        virtual.refresh_from_db()
        deleted.refresh_from_db()
        self.assertEqual(excluded_class.status, "in_progress")
        self.assertEqual(virtual.status, "completed")
        self.assertEqual(deleted.status, "in_progress")

    def test_completion_applies_across_facilities_and_includes_old_encounters(self):
        first = self.make_encounter(created_at=MIDNIGHT - timedelta(days=30))
        self.facility = self.create_facility(user=self.user)
        self.organization = self.create_facility_organization(facility=self.facility)
        second = self.make_encounter()
        self.assertEqual(self.run_task(), 2)
        for encounter in (first, second):
            encounter.refresh_from_db()
            self.assertEqual(encounter.status, "completed")

    def test_cutoff_excludes_new_encounters_and_future_starts(self):
        excluded = [
            self.make_encounter(created_at=MIDNIGHT),
            self.make_encounter(created_at=MIDNIGHT + timedelta(minutes=1)),
            self.make_encounter(period={"start": MIDNIGHT.isoformat()}),
            self.make_encounter(period={"start": "2026-11-25T18:31:00+00:00"}),
            self.make_encounter(period={"start": "2026-11-26T00:01:00"}),
            self.make_encounter(period={"start": "invalid"}),
        ]
        self.make_encounter(period={"start": "2026-11-25T18:29:00+00:00"})
        self.make_encounter(period={"start": "2026-11-25T23:59:00"})
        self.make_encounter(period={})
        self.assertEqual(self.run_task(), 3)
        for encounter in excluded:
            encounter.refresh_from_db()
            self.assertEqual(encounter.status, "in_progress")

    def test_time_limit_is_applied_per_class(self):
        same_day = self.make_encounter()
        too_recent = self.make_encounter(encounter_class="obsenc")
        started_too_recently = self.make_encounter(
            encounter_class="obsenc", created_at=MIDNIGHT - timedelta(hours=25)
        )
        old = self.make_encounter(
            encounter_class="obsenc",
            created_at=MIDNIGHT - timedelta(hours=25),
            period={"start": (MIDNIGHT - timedelta(hours=24, seconds=1)).isoformat()},
        )
        with configure([AMB, {"encounter_class": "obsenc", "time_limit_hours": 24}]):
            self.assertEqual(self.run_task(), 2)
        for encounter, expected in (
            (same_day, "completed"),
            (too_recent, "in_progress"),
            (started_too_recently, "in_progress"),
            (old, "completed"),
        ):
            encounter.refresh_from_db()
            self.assertEqual(encounter.status, expected)

    def test_default_cutoff_uses_beat_timezone_even_when_execution_is_delayed(self):
        before = self.make_encounter()
        after = self.make_encounter(created_at=MIDNIGHT + timedelta(seconds=1))
        with patch(
            "encounter_auto_complete.tasks.timezone.now",
            return_value=MIDNIGHT + timedelta(hours=1),
        ):
            self.assertEqual(complete_encounters.run(), 1)
        before.refresh_from_db()
        after.refresh_from_db()
        self.assertEqual(before.status, "completed")
        self.assertEqual(after.status, "in_progress")
        self.assertEqual(
            before.status_history["history"][-1]["scheduled_for"], MIDNIGHT.isoformat()
        )

    def test_history_period_and_automated_attribution_are_saved_once(self):
        original_entry = {
            "status": "in_progress",
            "moved_at": "2026-11-25T22:00:00+05:30",
        }
        encounter = self.make_encounter(status_history={"history": [original_entry]})
        completed_at = MIDNIGHT + timedelta(minutes=2)
        with patch(
            "encounter_auto_complete.tasks.timezone.now", return_value=completed_at
        ):
            self.assertEqual(self.run_task(), 1)
        encounter.refresh_from_db()
        self.assertEqual(encounter.status_history["history"][0], original_entry)
        self.assertEqual(
            encounter.status_history["history"][-1],
            {
                "status": "completed",
                "moved_at": completed_at.isoformat(),
                "source": "encounter_auto_complete",
                "scheduled_for": MIDNIGHT.isoformat(),
            },
        )
        self.assertEqual(encounter.period["end"], completed_at.isoformat())
        self.assertIsNone(encounter.updated_by_id)
        modified_date = encounter.modified_date
        self.assertEqual(self.run_task(), 0)
        encounter.refresh_from_db()
        self.assertEqual(len(encounter.status_history["history"]), 2)
        self.assertEqual(encounter.modified_date, modified_date)

    def test_existing_period_end_and_empty_history_are_supported(self):
        end = (MIDNIGHT - timedelta(minutes=30)).isoformat()
        encounter = self.make_encounter(period={"end": end}, status_history={})
        self.assertEqual(self.run_task(), 1)
        encounter.refresh_from_db()
        self.assertEqual(encounter.period["end"], end)
        self.assertEqual(len(encounter.status_history["history"]), 1)

    def make_associations(self, encounter):
        location = baker.make(
            FacilityLocation,
            facility=self.facility,
            current_encounter=encounter,
            operational_status="O",
            system_availability_status="occupied",
        )
        association = baker.make(
            FacilityLocationEncounter,
            location=location,
            encounter=encounter,
            status="active",
            start_datetime=MIDNIGHT - timedelta(hours=1),
        )
        device = baker.make(Device, facility=self.facility, current_encounter=encounter)
        history = baker.make(
            DeviceEncounterHistory,
            device=device,
            encounter=encounter,
            start=MIDNIGHT - timedelta(hours=1),
        )
        return location, association, device, history

    def test_completion_releases_location_and_device_associations(self):
        encounter = self.make_encounter()
        location, association, device, history = self.make_associations(encounter)
        self.assertEqual(self.run_task(), 1)
        for obj in (location, association, device, history):
            obj.refresh_from_db()
        self.assertIsNone(location.current_encounter_id)
        self.assertEqual(location.system_availability_status, "available")
        self.assertEqual(location.operational_status, "U")
        self.assertEqual(association.status, "completed")
        self.assertIsNotNone(association.end_datetime)
        self.assertIsNone(device.current_encounter_id)
        self.assertIsNotNone(history.end)

    def test_failure_rolls_back_cleanup_and_retries_with_the_original_cutoff(self):
        encounter = self.make_encounter()
        location, association, device, history = self.make_associations(encounter)
        with (
            patch.object(Encounter, "save", side_effect=OperationalError("temporary")),
            patch.object(complete_encounters, "retry", side_effect=Retry()) as retry,
            self.assertRaises(Retry),
        ):
            self.run_task()
        self.assertEqual(
            retry.call_args.kwargs["kwargs"], {"cutoff": MIDNIGHT.isoformat()}
        )
        for obj in (encounter, location, association, device, history):
            obj.refresh_from_db()
        self.assertEqual(encounter.status, "in_progress")
        self.assertEqual(encounter.status_history, {"history": []})
        self.assertEqual(location.current_encounter_id, encounter.id)
        self.assertEqual(association.status, "active")
        self.assertEqual(device.current_encounter_id, encounter.id)
        self.assertIsNone(history.end)

        later = self.make_encounter(created_at=MIDNIGHT + timedelta(hours=1))
        with patch(
            "encounter_auto_complete.tasks.timezone.now",
            return_value=MIDNIGHT + timedelta(days=1),
        ):
            self.assertEqual(self.run_task(), 1)
        later.refresh_from_db()
        self.assertEqual(later.status, "in_progress")

    def test_failing_encounter_is_rolled_back_and_does_not_block_others(self):
        failing = self.make_encounter()
        _, _, device, history = self.make_associations(failing)
        other = self.make_encounter()

        def close_locations(encounter):
            if encounter.pk == failing.pk:
                raise ValueError("bad data")
            close_related_location_from_encounter(encounter)

        with (
            patch(
                "encounter_auto_complete.tasks.close_related_location_from_encounter",
                side_effect=close_locations,
            ),
            self.assertLogs("encounter_auto_complete.tasks", "ERROR") as logs,
        ):
            self.assertEqual(self.run_task(), 1)
        self.assertIn(str(failing.pk), logs.output[0])
        for obj in (failing, other, device, history):
            obj.refresh_from_db()
        self.assertEqual(failing.status, "in_progress")
        self.assertEqual(other.status, "completed")
        # Device cleanup ran before the failure and was rolled back with it.
        self.assertEqual(device.current_encounter_id, failing.id)
        self.assertIsNone(history.end)
