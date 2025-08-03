from django.apps import AppConfig
import sys


class PmAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pm_app'
    def ready(self):
            # We only want this to run for the 'runserver' command
            if 'runserver' not in sys.argv:
                return

            # NOTE: Imports that depend on the app registry (like models)
            # or URLconfs must be done inside ready(), not at the top level.
            from django.urls import get_resolver
            from django.urls.exceptions import NoReverseMatch
            
            print("--- PROJECT URLS ---")
            
            resolver = get_resolver()
            
            # This is a simplified version of the logic from Method 2
            for pattern in sorted(resolver.url_patterns, key=lambda p: str(p.pattern)):
                try:
                    # We just print the pattern directly here for simplicity
                    print(f"URL: /{str(pattern.pattern)}")
                except Exception:
                    # Some patterns might not be simple strings
                    pass
            
            print("--------------------")