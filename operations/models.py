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

    value = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    @property
    def text_value(self):
        if self.event_schema and self.event_schema.data_type == 'text':
            return self.value
        return None

    @text_value.setter
    def text_value(self, val):
        if val is not None:
            self.value = val

    @property
    def num_value(self):
        if self.event_schema and self.event_schema.data_type == 'number':
            return self.value
        return None

    @num_value.setter
    def num_value(self, val):
        if val is not None:
            self.value = val

    @property
    def bool_value(self):
        if self.event_schema and self.event_schema.data_type == 'boolean':
            return self.value
        return None

    @bool_value.setter
    def bool_value(self, val):
        if val is not None:
            self.value = val

    @property
    def date_value(self):
        if self.event_schema and self.event_schema.data_type == 'date':
            if isinstance(self.value, str):
                from django.utils.dateparse import parse_date
                return parse_date(self.value)
            return self.value
        return None

    @date_value.setter
    def date_value(self, val):
        from datetime import date
        if val is not None:
            if isinstance(val, date):
                self.value = val.isoformat()
            else:
                self.value = val

    def get_value(self):
        if self.event_schema and self.event_schema.data_type == 'date':
            if isinstance(self.value, str):
                from django.utils.dateparse import parse_date
                parsed = parse_date(self.value)
                return parsed if parsed is not None else self.value
        return self.value

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
