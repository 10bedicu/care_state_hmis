from django.apps import AppConfig

PLUGIN_NAME = "appointment_invoice_payment"


class AppointmentInvoicePaymentConfig(AppConfig):
    name = PLUGIN_NAME

    def ready(self):
        import appointment_invoice_payment.signals  # noqa
