from typing import Any, List, Optional, Tuple

from django.db import models, transaction
from django.db.models import BooleanField, Max, Q, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from safedelete.models import SOFT_DELETE, SOFT_DELETE_CASCADE

from core.safedelete import BaseSafeDeleteModel, SafeDeleteManager

from accounts.models import User
from people.models import Person

from .utils import validate_and_cast_value

DATA_TYPE_TEXT = 'text'
DATA_TYPE_NUMBER = 'number'
DATA_TYPE_DATE = 'date'
DATA_TYPE_BOOLEAN = 'boolean'

DATA_TYPE_CHOICES = [
    (DATA_TYPE_TEXT, 'متن'),
    (DATA_TYPE_NUMBER, 'عدد'),
    (DATA_TYPE_DATE, 'تاریخ'),
    (DATA_TYPE_BOOLEAN, 'بولین'),
]

METADATA_SOURCE_PEM = 'pem'
METADATA_SOURCE_M = 'm'
METADATA_SOURCE_NONE = ''

METADATA_SOURCE_CHOICES = [
    (METADATA_SOURCE_PEM, 'متادیتای شخص-رویداد'),
    (METADATA_SOURCE_M, 'متادیتای شخص'),
    (METADATA_SOURCE_NONE, 'غیرفعال'),
]


class EventSchemaManager(SafeDeleteManager):
    def with_user_permissions(self, event, user):
        from .services import get_active_event_schemas_with_user_permissions
        return get_active_event_schemas_with_user_permissions(event, user)


class Event(BaseSafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    name = models.CharField(max_length=100)
    last_start_time = models.DateTimeField(null=True, blank=True)
    last_stop_time = models.DateTimeField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    participants = models.ManyToManyField(
        Person,
        through='PersonEventMetadata',
        related_name='events',
    )
    is_active = models.BooleanField(default=False)
    created_at = models.DateField(auto_now_add=True)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.is_active:
                Event.objects.filter(is_active=True).exclude(id=self.id).update(
                    is_active=False,
                    last_stop_time=timezone.now(),
                )
            super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
        ]
    
        constraints = [
            models.UniqueConstraint(
                fields=['is_active'],
                condition=models.Q(is_active=True),
                name='unique_single_active_event'
            )
    ]


class PersonEventMetadata(BaseSafeDeleteModel):
    _safedelete_policy = SOFT_DELETE

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='pems')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='pems')
    data = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.person}: ({self.event.name}) -> {self.data}"

    class Meta:
        unique_together = ('person', 'event')
        indexes = [
            models.Index(fields=['person', 'event']),
            models.Index(fields=['updated_at']),
        ]


class EventSchema(BaseSafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='schemas')
    column_name = models.CharField(max_length=100)
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES)
    is_required = models.BooleanField(default=False)
    default_value = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    metadata_source = models.CharField(
        max_length=20,
        choices=METADATA_SOURCE_CHOICES,
        default=METADATA_SOURCE_NONE,
        blank=True,
    )
    metadata_key = models.CharField(max_length=100, blank=True)

    objects = EventSchemaManager()

    def get_data(self, person) -> Tuple[Optional[Any], str, str]:
        from .services import resolve_schema_data
        return resolve_schema_data(self, person)

    def __str__(self):
        return f"{self.column_name} ({self.event.name})"


class Path(BaseSafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    name = models.CharField(max_length=100)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='paths')
    path_description = models.CharField(max_length=100)
    created_at = models.DateField(auto_now_add=True)
    allow_duplicate_checkin = models.BooleanField(default=False)
    enforce_checkpoint_order = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.event.name})"


class Checkpoint(BaseSafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    name = models.CharField(max_length=30)
    color = models.CharField(max_length=30, blank=True)
    path = models.ForeignKey(Path, on_delete=models.CASCADE, related_name='checkpoints')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='checkpoints')
    order = models.PositiveIntegerField(default=0)
    location_description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_mandatory = models.BooleanField(default=False)
    created_at = models.DateField(auto_now_add=True)
    allow_duplicate_checkin = models.BooleanField(default=False)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.name


class CheckpointSchema(BaseSafeDeleteModel):
    _safedelete_policy = SOFT_DELETE

    checkpoint = models.ForeignKey(Checkpoint, on_delete=models.CASCADE, related_name='schemas')
    event_schema = models.ForeignKey(EventSchema, on_delete=models.CASCADE, related_name='cp_schemas')
    can_view = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_fill = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.event_schema.column_name} @ {self.checkpoint.name}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['checkpoint', 'event_schema'],
                name='unique_checkpoint_schema',
            )
        ]
