from django.core.management.base import BaseCommand
from chat.models import ToolLog

class Command(BaseCommand):
    help = 'Displays the most recent tool logs'

    def handle(self, *args, **options):
        count = ToolLog.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Total tool logs: {count}"))

        logs = ToolLog.objects.all().order_by('-created_at')[:5]
        for log in logs:
            self.stdout.write("-" * 30)
            self.stdout.write(f"Time: {log.created_at}")
            self.stdout.write(f"Tool: {log.tool_name}")
            self.stdout.write(f"Input: {log.input_args}")
            # Show first 200 chars of output
            output = log.output_result[:200] + "..." if len(log.output_result) > 200 else log.output_result
            self.stdout.write(f"Output: {output}")
