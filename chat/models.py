from django.db import models

class ToolLog(models.Model):
    tool_name = models.CharField(max_length=255)
    input_args = models.TextField()
    output_result = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tool_name} at {self.created_at}"


class ChatSession(models.Model):
    title = models.CharField(max_length=255, blank=True, default='')
    history = models.TextField(default='[]')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or f"Chat {self.id}"


class Booking(models.Model):
    booking_ref = models.CharField(max_length=50, unique=True)
    booking_type = models.CharField(max_length=10)  # "flight" or "hotel"
    duffel_order_id = models.CharField(max_length=100, blank=True, default='')
    passenger_name = models.CharField(max_length=200)
    passenger_email = models.EmailField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(max_length=20, default='confirmed')
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.booking_type.title()} {self.booking_ref} - {self.passenger_name}"
