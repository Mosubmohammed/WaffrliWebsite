from django.apps import AppConfig


class WaffrliConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'waffrli'


    def ready(self):
        """Import signal handlers when the app is ready"""
        import waffrli.signals  