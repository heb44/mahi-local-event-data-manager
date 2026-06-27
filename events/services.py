from typing import Any, List, Optional, Tuple
from django.db.models import Q, Max, BooleanField, Value
from django.db.models.functions import Coalesce

# Constants duplicated or imported to prevent circular imports
DATA_TYPE_TEXT = 'text'
DATA_TYPE_NUMBER = 'number'
DATA_TYPE_DATE = 'date'
DATA_TYPE_BOOLEAN = 'boolean'

METADATA_SOURCE_PEM = 'pem'
METADATA_SOURCE_M = 'm'


def resolve_schema_data(schema, person) -> Tuple[Optional[Any], str, str]:
    """
    Retrieves data for a person for a given schema.
    Relocated from EventSchema.get_data.
    """
    from .utils import validate_and_cast_value

    messages: List[str] = []

    sources = []
    if schema.metadata_source == METADATA_SOURCE_PEM:
        sources.append(METADATA_SOURCE_PEM)
    elif schema.metadata_source == METADATA_SOURCE_M:
        sources.append(METADATA_SOURCE_M)
    sources.append('default')

    for source_key in sources:
        raw_value = None
        if source_key == METADATA_SOURCE_PEM:
            pem_list = getattr(person, 'event_pems', person.pems.filter(event_id=schema.event_id))
            pem = next((p for p in pem_list), None)
            if pem:
                raw_value = pem.data.get(schema.metadata_key)
        elif source_key == METADATA_SOURCE_M:
            raw_value = person.metadata.get(schema.metadata_key)
        elif source_key == 'default':
            raw_value = schema.default_value

        if not raw_value or raw_value == '':
            continue

        is_valid, casted_value = validate_and_cast_value(schema.data_type, raw_value)
        if is_valid:
            return (casted_value, source_key, ' '.join(messages))

        messages.append(
            f"Value '{raw_value}' from source '{source_key}' ignored due to type mismatch."
        )

    return (None, '', ' '.join(messages))


def get_active_event_schemas_with_user_permissions(event, user):
    """
    Fetches schemas with user permission annotations.
    Relocated from EventSchemaManager.with_user_permissions.
    """
    from .models import EventSchema

    checkpoint_filter = Q(
        cp_schemas__checkpoint__path__event=event,
        cp_schemas__checkpoint__user=user,
        cp_schemas__checkpoint__is_active=True,
    )

    return EventSchema.objects.filter(
        event=event,
        is_active=True,
    ).annotate(
        can_view=Coalesce(
            Max(
                'cp_schemas__can_view',
                filter=checkpoint_filter,
                output_field=BooleanField(),
            ),
            Value(False),
        ),
        can_edit=Coalesce(
            Max(
                'cp_schemas__can_edit',
                filter=checkpoint_filter,
                output_field=BooleanField(),
            ),
            Value(False),
        ),
        can_fill=Coalesce(
            Max(
                'cp_schemas__can_fill',
                filter=checkpoint_filter,
                output_field=BooleanField(),
            ),
            Value(False),
        ),
    ).order_by('column_name')
