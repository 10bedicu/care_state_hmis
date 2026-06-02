from django.urls import path

from encounter_identifiers.viewsets import FacilityEncounterIdentifierConfigViewSet


facility_identifier_config_list = FacilityEncounterIdentifierConfigViewSet.as_view(
	{"get": "retrieve", "post": "create", "put": "update"}
)

urlpatterns = [
	path(
		"facility/<uuid:facility_external_id>/identifier-config/",
		facility_identifier_config_list,
		name="facility-identifier-config-retrieve",
	),
]
