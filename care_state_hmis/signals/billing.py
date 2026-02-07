from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from rest_framework.exceptions import ValidationError

from care.emr.locks.billing import InvoiceCreateLock, InvoiceLock
from care.emr.models.charge_item import ChargeItem
from care.emr.models.invoice import Invoice
from care.emr.models.payment_reconciliation import PaymentReconciliation
from care.emr.models.scheduling.booking import TokenBooking
from care.emr.resources.account.sync_items import rebalance_account_task
from care.emr.resources.charge_item.spec import ChargeItemStatusOptions
from care.emr.resources.invoice.default_expression_evaluator import (
    evaluate_invoice_identifier_default_expression,
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


@receiver(post_save, sender=TokenBooking)
def handle_payment_on_appointment_scheduled(
    sender, instance: TokenBooking, created: bool, **kwargs
):
    if not created or instance.charge_item:
        return

    charge_item = instance.charge_item
    if charge_item.status == ChargeItemStatusOptions.billable.value:
        # create invoice
        try:
            with InvoiceCreateLock():
                invoice = Invoice.objects.create(
                    facility=charge_item.facility,
                    account=charge_item.account,
                    patient=instance.patient,
                    status=InvoiceStatusOptions.draft.value,
                    number=evaluate_invoice_identifier_default_expression(
                        charge_item.facility
                    ),
                    charge_items=[charge_item.id],
                )
        except ObjectLocked as e:
            raise ValidationError("Invoice creation failed") from e

        charge_item.paid_invoice = invoice
        charge_item.status = ChargeItemStatusOptions.billed.value
        charge_item.save()
        sync_invoice_items(invoice)
        invoice.save()

        # issue invoice
        with InvoiceLock(invoice):
            invoice.status = InvoiceStatusOptions.issued.value
            invoice.issue_date = care_now()
            invoice.save()
            rebalance_account_task(charge_item.account.id)

        ### Record payment and balenc invoice will be taken care by the handle_payment_on_invoice_issued signal
        # # record payment
        # PaymentReconciliation.objects.create(
        #     facility=charge_item.facility,
        #     account=charge_item.account,
        #     amount=charge_item.total_price,
        #     tendered_amount=charge_item.total_price,
        #     returned_amount=0,
        #     is_credit_note=False,
        #     issuer_type=PaymentReconciliationIssuerTypeOptions.patient.value,
        #     kind=PaymentReconciliationKindOptions.deposit.value,
        #     method=PaymentReconciliationPaymentMethodOptions.cash.value,
        #     outcome=PaymentReconciliationOutcomeOptions.complete.value,
        #     reconciliation_type=PaymentReconciliationTypeOptions.payment.value,
        #     status=PaymentReconciliationStatusOptions.active.value,
        #     payment_datetime=care_now(),
        #     target_invoice=invoice,
        # )
        # rebalance_account_task(charge_item.account.id)

        # # balance invoice
        # with InvoiceLock(invoice):
        #     charge_item.status = ChargeItemStatusOptions.paid.value
        #     charge_item.paid_invoice = invoice
        #     charge_item.paid_on = care_now()
        #     charge_item.save()
        #     invoice.status = InvoiceStatusOptions.balanced.value
        #     invoice.save()
        #     rebalance_account_task(charge_item.account.id)


@receiver(pre_save, sender=Invoice)
def handle_payment_on_invoice_issued(sender, instance: Invoice, **kwargs):
    if not instance.pk:
        return

    previous = sender.objects.get(pk=instance.pk)

    if (
        previous.status == InvoiceStatusOptions.draft.value
        and instance.status == InvoiceStatusOptions.issued.value
    ):

        def record_payment():
            # record payment
            PaymentReconciliation.objects.create(
                facility=instance.facility,
                account=instance.account,
                amount=instance.total_net,
                tendered_amount=instance.total_net,
                returned_amount=0,
                is_credit_note=False,
                issuer_type=PaymentReconciliationIssuerTypeOptions.patient.value,
                kind=PaymentReconciliationKindOptions.deposit.value,
                method=PaymentReconciliationPaymentMethodOptions.cash.value,
                outcome=PaymentReconciliationOutcomeOptions.complete.value,
                reconciliation_type=PaymentReconciliationTypeOptions.payment.value,
                status=PaymentReconciliationStatusOptions.active.value,
                payment_datetime=care_now(),
                target_invoice=instance,
            )
            rebalance_account_task(instance.account.id)

            # balance invoice
            with InvoiceLock(instance):
                ChargeItem.objects.filter(
                    account=instance.account,
                    status=ChargeItemStatusOptions.billed.value,
                    id__in=instance.charge_items,
                ).update(
                    status=ChargeItemStatusOptions.paid.value,
                    paid_invoice=instance,
                    paid_on=care_now(),
                )
                instance.status = InvoiceStatusOptions.balanced.value
                instance.save()
                rebalance_account_task(instance.account.id)

        transaction.on_commit(record_payment)
