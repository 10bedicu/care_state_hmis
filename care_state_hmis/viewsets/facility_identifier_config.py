from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from care.emr.api.viewsets.base import (
    EMRBaseViewSet,
    EMRCreateMixin,
    EMRRetrieveMixin,
    EMRUpdateMixin,
)
from care.facility.models import Facility
from care.security.authorization import AuthorizationController
from care.utils.shortcuts import get_object_or_404

from care_state_hmis.models import FacilityEncounterIdentifierConfig
from care_state_hmis.spec import (
    FacilityEncounterIdentifierConfigReadSpec,
    FacilityEncounterIdentifierConfigWriteSpec,
)


class FacilityEncounterIdentifierConfigViewSet(
    EMRCreateMixin,
    EMRUpdateMixin,
    EMRRetrieveMixin,
    EMRBaseViewSet,
):
    database_model = FacilityEncounterIdentifierConfig
    pydantic_model = FacilityEncounterIdentifierConfigWriteSpec
    pydantic_read_model = FacilityEncounterIdentifierConfigReadSpec
    pydantic_retrieve_model = FacilityEncounterIdentifierConfigReadSpec
    pydantic_update_model = FacilityEncounterIdentifierConfigWriteSpec

    def get_facility(self):
        return get_object_or_404(
            Facility, external_id=self.kwargs["facility_external_id"]
        )

    def get_object(self):
        facility = self.get_facility()
        self.authorize_facility(facility)
        return get_object_or_404(
            FacilityEncounterIdentifierConfig, facility=facility
        )

    def authorize_facility(self, facility):
        if not AuthorizationController.call(
            "can_update_facility_obj", self.request.user, facility
        ):
            raise PermissionDenied(
                "You do not have permission to configure this facility"
            )

    def validate_data(self, instance, model_obj=None):
        if model_obj is not None:
            return
        facility = self.get_facility()
        if FacilityEncounterIdentifierConfig.objects.filter(facility=facility).exists():
            raise ValidationError(
                {"facility": "Configuration already exists for this facility."}
            )

    def authorize_create(self, instance):
        self.authorize_facility(self.get_facility())

    def authorize_update(self, request_obj, model_instance):
        self.authorize_facility(self.get_facility())

    def get_serializer_create_context(self):
        return {"facility": self.get_facility()}

    def get_serializer_update_context(self):
        return {"facility": self.get_facility()}

    def retrieve(self, request, *args, **kwargs):
        facility = self.get_facility()
        self.authorize_facility(facility)
        instance = FacilityEncounterIdentifierConfig.objects.filter(facility=facility).first()
        if not instance:
            return Response({})
        data = self.get_retrieve_pydantic_model().serialize(instance, request.user).to_json()
        return Response(data)