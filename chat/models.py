from django.db import models

class ToolLog(models.Model):
    tool_name = models.CharField(max_length=255)
    input_args = models.TextField()
    output_result = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tool_name} at {self.created_at}"
