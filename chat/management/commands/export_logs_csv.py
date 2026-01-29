import csv
from django.core.management.base import BaseCommand
from chat.models import ToolLog

class Command(BaseCommand):
    help = "Export ToolLog to CSV"

    def handle(self, *args, **kwargs):
        with open("tool_log.csv", "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)

            # Header (MATCH THE MODEL)
            writer.writerow([
                "id",
                "created_at",
                "tool_name",
                "input_args",
                "output_result",
            ])

            # Rows
            for log in ToolLog.objects.all().order_by("created_at"):
                writer.writerow([
                    log.id,
                    log.created_at,
                    log.tool_name,
                    log.input_args,
                    log.output_result,
                ])

        self.stdout.write(
            self.style.SUCCESS("Tool log exported to tool_log.csv")
        )
