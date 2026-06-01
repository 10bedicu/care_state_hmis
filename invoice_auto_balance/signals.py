from django.db import transaction
from django.db.models import Case, Sum, When
from django.db.models.signals import post_save
from django.dispatch import receiver

from care.emr.locks.billing import InvoiceLock
from care.emr.models.charge_item import ChargeItem
from care.emr.models.payment_reconciliation import PaymentReconciliation
from care.emr.resources.account.sync_items import rebalance_account_task
from care.emr.resources.charge_item.spec import ChargeItemStatusOptions
from care.emr.resources.invoice.spec import InvoiceStatusOptions
from care.emr.resources.payment_reconciliation.spec import (
    PaymentReconciliationOutcomeOptions,
    PaymentReconciliationStatusOptions,
)
from care.utils.time_util import care_now


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
