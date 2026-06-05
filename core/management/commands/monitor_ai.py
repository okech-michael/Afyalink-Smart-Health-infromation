from django.core.management.base import BaseCommand

from core.ai_monitor import run_ai_monitoring


class Command(BaseCommand):
    help = 'Run AI monitoring system: predicts drug shortages and sends supplier notifications.'

    def handle(self, *args, **options):
        results = run_ai_monitoring()
        
        shortages = results.get('drug_shortages', [])
        if shortages:
            self.stdout.write(self.style.WARNING(
                f"Detected {len(shortages)} drug shortage alert(s)."
            ))
            for alert in shortages:
                self.stdout.write(
                    f"- {alert.drug_stock.drug_name} at {alert.facility.name}: "
                    f"runs out in {alert.days_until_runout} days [{alert.severity}]"
                )
        else:
            self.stdout.write(self.style.SUCCESS('No drug shortage alerts detected.'))
