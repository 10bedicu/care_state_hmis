from datetime import timedelta

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from care.emr.models.scheduling.booking import TokenBooking
from care.emr.models.scheduling.token import Token, TokenCategory, TokenQueue
from care.emr.resources.scheduling.token.spec import TokenStatusOptions
from care.utils.lock import Lock


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

    #  get or create a queue
    token_date = timezone.make_naive(
        instance.token_slot.start_datetime + timedelta(seconds=1)
    ).date()
    filters = {
        "facility": instance.token_slot.resource.facility,
        "resource": instance.token_slot.resource,
        "date": token_date,
    }
    queue_exists = TokenQueue.objects.filter(**filters).exists()
    filters["system_generated"] = True
    queue = TokenQueue.objects.filter(**filters).first()
    if not queue:
        filters["name"] = "System Generated"
        if not queue_exists:
            filters["is_primary"] = True
        queue = TokenQueue.objects.create(**filters)

    # create a token for the patient
    with Lock(f"booking:token:{queue.id}"), transaction.atomic():
        number = Token.objects.filter(queue=queue, category=category).count() + 1
        token = Token.objects.create(
            facility=instance.token_slot.resource.facility,
            queue=queue,
            category=category,
            number=number,
            status=TokenStatusOptions.CREATED.value,
            note="",
            booking=instance,
            patient=instance.patient,
        )
        instance.token = token
        instance.save(update_fields=["token"])
