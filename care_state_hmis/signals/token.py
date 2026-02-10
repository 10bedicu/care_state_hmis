from django.db.models.signals import post_save
from django.dispatch import receiver

from care.emr.api.viewsets.scheduling.booking import TokenBookingViewSet
from care.emr.models.scheduling.booking import TokenBooking
from care.emr.models.scheduling.token import TokenCategory


@receiver(post_save, sender=TokenBooking)
def handle_token_on_appointment_scheduled(
    sender, instance: TokenBooking, created: bool, **kwargs
):
    if not created or instance.token:
        return

    # get the default token category for the resource_type
    category = TokenCategory.objects.filter(
        facility=instance.token_slot.resource.facility,
        resource_type=instance.token_slot.resource.resource_type,
        default=True,
    ).first()

    if not category:
        return

    # generate a token for the patient
    TokenBookingViewSet.generate_token_handler(instance, category)
