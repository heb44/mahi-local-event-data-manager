from django.db import models
from simple_history.models import HistoricalRecords
from safedelete.models import SOFT_DELETE_CASCADE

from core.safedelete import BaseSafeDeleteModel


class Person(BaseSafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    birth_date = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.name} {self.last_name}"

    class Meta:
        indexes = [
            models.Index(fields=['name', 'last_name', 'phone_number']),
            models.Index(fields=['deleted'], name='people_pers_deleted_4b6f7d_idx'),
        ]
