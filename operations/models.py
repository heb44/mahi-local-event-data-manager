from django.db import models
from simple_history.models import HistoricalRecords
from safedelete.models import SOFT_DELETE_CASCADE

from accounts.models import User
from core.safedelete import BaseSafeDeleteModel
from people.models import Person
from events.models import Checkpoint, EventSchema


class CheckIn(BaseSafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='checkins')
    checkpoint = models.ForeignKey(Checkpoint, on_delete=models.CASCADE, related_name='checkins')

    is_valid = models.BooleanField()
    is_approved = models.BooleanField()
    description = models.CharField(max_length=400, blank=True)
    timestamp = models.DateTimeField(auto_now=True)
    pending = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.person.name} @ {self.checkpoint.name} @ {self.timestamp}"

    class Meta:
        indexes = [
            models.Index(fields=['person', 'checkpoint']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['deleted']),
        ]


class CheckInData(BaseSafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    check_in = models.ForeignKey(CheckIn, on_delete=models.CASCADE, related_name="data")
    event_schema = models.ForeignKey(EventSchema, on_delete=models.CASCADE, related_name="data")

    text_value = models.TextField(null=True)
    num_value = models.FloatField(null=True)
    bool_value = models.BooleanField(null=True)
    date_value = models.DateField(null=True)
    created_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    def get_value(self):
        if self.text_value is not None:
            return self.text_value
        if self.num_value is not None:
            return self.num_value
        if self.bool_value is not None:
            return self.bool_value
        if self.date_value is not None:
            return self.date_value
        return None

    def __str__(self):
        value = self.get_value()
        return f"{self.event_schema.column_name}: {value if value is not None else ''}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['check_in', 'event_schema'],
                condition=models.Q(deleted__isnull=True),
                name='unique_active_checkin_data'
            )
        ]
        indexes = [
            models.Index(fields=['event_schema']),
            models.Index(fields=['created_at']),
            models.Index(fields=['deleted']),
        ]
