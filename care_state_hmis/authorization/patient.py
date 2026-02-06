
from care.security.authorization.base import (
    AuthorizationController,
    AuthorizationHandler,
)
from care.security.authorization.patient import PatientAccess
from care.security.models import RolePermission
from care.security.permissions.patient import PatientPermissions


class HMISPatientAccess(AuthorizationHandler):
    def find_roles_on_patient(self, user, patient):
        patient_access = PatientAccess()
        return patient_access.find_roles_on_patient(user, patient)

    def can_view_patient_obj(self, user, patient):
        if self.check_permission_in_organization(
            [PatientPermissions.can_list_patients.name], user
        ):
            return True
        user_roles = self.find_roles_on_patient(user, patient)
        return RolePermission.objects.filter(
            permission__slug__in=[PatientPermissions.can_list_patients.name],
            role__in=user_roles,
        ).exists()

    def can_write_patient_obj(self, user, patient):
        if self.check_permission_in_organization(
            [PatientPermissions.can_write_patient.name], user
        ):
            return True
        user_roles = self.find_roles_on_patient(user, patient)
        return RolePermission.objects.filter(
            permission__slug__in=[PatientPermissions.can_write_patient.name],
            role__in=user_roles,
        ).exists()

AuthorizationController.override_authz_controllers.append(HMISPatientAccess)
