from django.apps import AppConfig

PLUGIN_NAME = "invoice_auto_balance"


class InvoiceAutoBalanceConfig(AppConfig):
    name = PLUGIN_NAME

    def ready(self):
        """
        Import models, signals, and other dependencies here to ensure
        Django's app registry is fully initialized before use.
        """

        import invoice_auto_balance.signals  # noqa
