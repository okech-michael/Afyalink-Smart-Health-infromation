from django.core.management.base import BaseCommand

from core.outbreaks import detect_outbreaks


class Command(BaseCommand):
    help = 'Run outbreak detection and send notifications for newly detected clusters.'

    def handle(self, *args, **options):
        alerts = detect_outbreaks()
        if alerts:
            self.stdout.write(self.style.SUCCESS(
                f"Detected and notified {len(alerts)} outbreak alert(s)."
            ))
            for alert in alerts:
                location = alert.sub_county or alert.county or 'Unknown region'
                self.stdout.write(f"- {alert.diagnosis} in {location}: {alert.case_count} cases")
        else:
            self.stdout.write(self.style.NOTICE('No new outbreak alerts were detected.'))
