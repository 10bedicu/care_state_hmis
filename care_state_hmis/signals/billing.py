from curses import meta
import logging
from django.db import transaction
from django.db.models import Case, Sum, When
from django.db.models.signals import post_save
from django.dispatch import receiver
from care.emr.models.encounter import Encounter
from care.emr.resources.scheduling.slot.spec import CANCELLED_STATUS_CHOICES
from rest_framework.exceptions import ValidationError

from care.emr.locks.billing import InvoiceCreateLock, InvoiceLock
from care.emr.models.charge_item import ChargeItem
from care.emr.models.invoice import Invoice
from care.emr.models.payment_reconciliation import PaymentReconciliation
from care.emr.models.scheduling.booking import TokenBooking
from care.emr.resources.scheduling.schedule.spec import SchedulableResourceTypeOptions
from care.emr.resources.account.sync_items import rebalance_account_task
from care.emr.resources.charge_item.spec import ChargeItemResourceOptions, ChargeItemStatusOptions
from care.emr.resources.invoice.default_expression_evaluator import (
    evaluate_invoice_identifier_default_expression,
)
from care.emr.resources.charge_item.apply_charge_item_definition import (
    apply_charge_item_definition,
)
from care.emr.resources.invoice.spec import InvoiceStatusOptions
from care.emr.resources.invoice.sync_items import sync_invoice_items
from care.emr.resources.payment_reconciliation.spec import (
    PaymentReconciliationIssuerTypeOptions,
    PaymentReconciliationKindOptions,
    PaymentReconciliationOutcomeOptions,
    PaymentReconciliationPaymentMethodOptions,
    PaymentReconciliationStatusOptions,
    PaymentReconciliationTypeOptions,
)
from care.utils.lock import ObjectLocked
from care.utils.time_util import care_now


@receiver(post_save, sender=TokenBooking, dispatch_uid="handle_appointment_invoice_payment")
def handle_appointment_invoice_payment(sender, instance, created, **kwargs):
    # Skip if no charge_item linked yet (e.g. initial INSERT before charge item is created)
    if not instance.charge_item_id:
        return
    # On updates, only proceed if charge_item was the field being set
    update_fields = kwargs.get("update_fields")
    if not created and (not update_fields or "charge_item" not in update_fields):
        return

    # Prevent duplicate processing
    if getattr(instance, "_processing_appointment_charge_item", False):
        return
    instance._processing_appointment_charge_item = True 

    default_charge_item = instance.charge_item
    # Skip processing if the default charge item is already paid
    if default_charge_item and default_charge_item.paid_invoice:
        return

    token_slot = instance.token_slot
    availability = token_slot.availability
    schedule = availability.schedule
    facility = schedule.resource.facility
    revisit_charge_item_definition = schedule.revisit_charge_item_definition

    last_booking = (
        TokenBooking.objects.exclude(status__in=CANCELLED_STATUS_CHOICES)
        .filter(
            patient=instance.patient,
            token_slot__availability__schedule__resource__facility=facility,
            token_slot__availability__schedule__resource__resource_type=SchedulableResourceTypeOptions.healthcare_service.value,
            charge_item__isnull=False,
            charge_item__status=ChargeItemStatusOptions.paid.value,
            token_slot__start_datetime__lte=token_slot.start_datetime,
        )
        .order_by("-token_slot__start_datetime")
    ).first()

    diff_days = None
    if last_booking and (booking_start_time := last_booking.charge_item.paid_on):
        new_booking_start_time = token_slot.start_datetime
        diff_days = (booking_start_time - new_booking_start_time).days

    charge_item = default_charge_item
    if (
        schedule.revisit_allowed_days
        and default_charge_item
        and diff_days is not None
        and abs(diff_days) <= schedule.revisit_allowed_days
    ):
        # Cancel the default charge item created by the view
        default_charge_item.delete()
        instance.charge_item = None

        # create new custom charge item if revisit_charge_item_definition is set
        if revisit_charge_item_definition:
            charge_item = apply_charge_item_definition(
                revisit_charge_item_definition,
                instance.patient,
                token_slot.resource.facility,
                quantity=1,
            )
            charge_item.service_resource = (
                ChargeItemResourceOptions.appointment.value
            )
            charge_item.service_resource_id = str(instance.external_id)
            charge_item.created_by = instance.created_by
            charge_item.updated_by = instance.updated_by
            charge_item.meta = {
                "automated": True,
            }
            charge_item.save()
            instance.charge_item = charge_item

        instance.save(update_fields=["charge_item"])

    if charge_item and charge_item.status == ChargeItemStatusOptions.billable.value:
        with transaction.atomic():
            # create invoice
            try:
                with InvoiceCreateLock():
                    invoice = Invoice.objects.create(
                        facility_id=charge_item.facility_id,
                        account_id=charge_item.account_id,
                        patient_id=instance.patient_id,
                        status=InvoiceStatusOptions.draft.value,
                        number=evaluate_invoice_identifier_default_expression(
                            charge_item.facility
                        ),
                        charge_items=[charge_item.id],
                        created_by=instance.created_by,
                        updated_by=instance.updated_by,
                        meta={
                            "automated": True,
                        }
                    )
            except ObjectLocked as e:
                raise ValidationError("Invoice creation failed") from e

            charge_item.paid_invoice = invoice
            charge_item.status = ChargeItemStatusOptions.billed.value
            charge_item.save(update_fields=["paid_invoice", "status"])
            sync_invoice_items(invoice)
            invoice.save(
                update_fields=[
                    "total_net",
                    "total_gross",
                    "total_price_components",
                    "charge_items_copy",
                ]
            )

            # issue invoice
            with InvoiceLock(invoice):
                invoice.status = InvoiceStatusOptions.issued.value
                invoice.issue_date = care_now()
                invoice.save(update_fields=["status", "issue_date"])

            # record payment
            PaymentReconciliation.objects.create(
                facility_id=charge_item.facility_id,
                account_id=charge_item.account_id,
                amount=charge_item.total_price,
                tendered_amount=charge_item.total_price,
                returned_amount=0,
                is_credit_note=False,
                issuer_type=PaymentReconciliationIssuerTypeOptions.patient.value,
                kind=PaymentReconciliationKindOptions.deposit.value,
                method=PaymentReconciliationPaymentMethodOptions.cash.value,
                outcome=PaymentReconciliationOutcomeOptions.complete.value,
                reconciliation_type=PaymentReconciliationTypeOptions.payment.value,
                status=PaymentReconciliationStatusOptions.active.value,
                payment_datetime=care_now(),
                target_invoice=invoice,
                created_by=instance.created_by,
                updated_by=instance.updated_by,
            )

    # Clean up the flag
    delattr(instance, "_processing_appointment_charge_item") 


@receiver(post_save, sender=PaymentReconciliation, dispatch_uid="handle_payment_reconciliation_rebalance")
def handle_payment_reconciliation_rebalance(sender, instance, **kwargs):
    if instance.status != PaymentReconciliationStatusOptions.active.value:
        return
    if instance.outcome != PaymentReconciliationOutcomeOptions.complete.value:
        return

    # Auto-balance the target invoice if fully paid
    if instance.target_invoice_id:
        invoice = instance.target_invoice
        if invoice.status == InvoiceStatusOptions.issued.value:
            # Calculate net paid using database aggregation
            totals = PaymentReconciliation.objects.filter(
                target_invoice_id=instance.target_invoice_id,
                outcome=PaymentReconciliationOutcomeOptions.complete.value,
                status=PaymentReconciliationStatusOptions.active.value,
            ).aggregate(
                total_payments=Sum(Case(When(is_credit_note=False, then="amount"))),
                total_credit_notes=Sum(Case(When(is_credit_note=True, then="amount"))),
            )
            net_paid = (totals["total_payments"] or 0) - (totals["total_credit_notes"] or 0)

            if net_paid >= invoice.total_gross:
                with transaction.atomic(), InvoiceLock(invoice):
                    ChargeItem.objects.filter(
                        account_id=invoice.account_id,
                        status=ChargeItemStatusOptions.billed.value,
                        id__in=invoice.charge_items,
                    ).update(
                        status=ChargeItemStatusOptions.paid.value,
                        paid_invoice=invoice,
                        paid_on=care_now(),
                    )
                    invoice.status = InvoiceStatusOptions.balanced.value
                    invoice.save(update_fields=["status"])

    rebalance_account_task(instance.account_id)
