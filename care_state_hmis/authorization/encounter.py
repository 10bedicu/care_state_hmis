from care.emr.resources.encounter.constants import COMPLETED_CHOICES
from care.security.authorization.base import (
    AuthorizationController,
    AuthorizationHandler,
)
from care.security.authorization.encounter import EncounterAccess
from care.security.permissions.encounter import EncounterPermissions


class HMISEncounterAccess(AuthorizationHandler):
    def check_permission_in_encounter(self, user, encounter, permission):
        encounter_access = EncounterAccess()
        return encounter_access.check_permission_in_encounter(user, encounter, permission)

    def can_restart_encounter_obj(self, user, encounter):
        """
        Check if the user has permission to restart the given encounter
        """
        # Only superusers or the user who updated the encounter can restart it
        if not user.is_superuser and encounter.updated_by != user:
            return False
        # Cannot write to a closed encounter
        if encounter.status not in COMPLETED_CHOICES:
            return False
        return self.check_permission_in_encounter(
            user, encounter, EncounterPermissions.can_write_encounter.name
        )


AuthorizationController.override_authz_controllers.append(HMISEncounterAccess)
