from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Core'
    
    def ready(self):
        """Initialize app on Django startup."""
        # Initialize OpenTelemetry tracing if enabled
        try:
            from apps.core.tracing import auto_init
            auto_init()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Tracing initialization failed: {e}")
