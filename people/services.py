from collections.abc import Callable
from typing import Any, TypedDict

from django.core.paginator import Page, Paginator
from django.db import transaction
from django.db.models import Q, QuerySet
from django.http import HttpRequest

from .models import Person

DEFAULT_PERSON_PAGE_SIZE = 10
VALID_PERSON_ORDER_FIELDS = ['id', 'name', 'last_name', 'birth_date']

MetadataHandler = Callable[[Person, dict[str, str]], None]


class PersonFilterParams(TypedDict):
    search_query: str
    search_fields_raw: str
    search_fields: list[str]
    metadata_key: str
    metadata_value: str
    order_by: str
    direction: str


class PersonListContext(TypedDict):
    page_obj: Page
    paginator: Paginator
    search_query: str
    search_fields: str
    search_fields_list: list[str]
    metadata_key: str
    metadata_value: str
    order_by: str
    direction: str


class PersonImportResult(TypedDict):
    errors: list[str]
    new_persons: int
    updated_persons: int
    extra_columns: list[str]


class PersonFilterService:
    @staticmethod
    def filter_sort_paginate(
        request: HttpRequest,
        base_queryset: QuerySet,
        page_size: int = DEFAULT_PERSON_PAGE_SIZE,
    ) -> PersonListContext:
        params = PersonFilterService._extract_params(request)
        queryset = PersonFilterService._apply_filters(base_queryset, params)
        queryset = PersonFilterService._apply_ordering(queryset, params)

        paginator = Paginator(queryset, page_size)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        return {
            'page_obj': page_obj,
            'paginator': paginator,
            'search_query': params['search_query'],
            'search_fields': params['search_fields_raw'],
            'search_fields_list': params['search_fields'],
            'metadata_key': params['metadata_key'],
            'metadata_value': params['metadata_value'],
            'order_by': params['order_by'].lstrip('-'),
            'direction': params['direction'],
        }

    @staticmethod
    def _extract_params(request: HttpRequest) -> PersonFilterParams:
        search_fields_raw = request.GET.get('sf', '').strip()
        search_fields = search_fields_raw.split(',') if search_fields_raw else []
        return {
            'search_query': request.GET.get('q', '').strip(),
            'search_fields_raw': search_fields_raw,
            'search_fields': search_fields,
            'metadata_key': request.GET.get('mk', '').strip(),
            'metadata_value': request.GET.get('mv', '').strip(),
            'order_by': request.GET.get('ob', 'id'),
            'direction': request.GET.get('dir', 'asc'),
        }

    @staticmethod
    def _apply_filters(queryset: QuerySet, params: PersonFilterParams) -> QuerySet:
        search_query = params['search_query']
        search_fields = params['search_fields']

        if search_query and search_fields:
            filter_q = Q()
            field_map = {
                'name': Q(name__icontains=search_query),
                'last_name': Q(last_name__icontains=search_query),
                'phone_number': Q(phone_number__icontains=search_query),
            }
            for field in search_fields:
                if field in field_map:
                    filter_q |= field_map[field]
            queryset = queryset.filter(filter_q)

        if 'metadata' in search_fields:
            if params['metadata_key'] and params['metadata_value']:
                queryset = queryset.filter(metadata__contains={params['metadata_key']: params['metadata_value']})
            elif params['metadata_key']:
                queryset = queryset.filter(metadata__has_key=params['metadata_key'])

        return queryset

    @staticmethod
    def _apply_ordering(queryset: QuerySet, params: PersonFilterParams) -> QuerySet:
        order_by = params['order_by']
        direction = params['direction']
        if order_by in VALID_PERSON_ORDER_FIELDS:
            if direction == 'desc':
                order_by = f'-{order_by}'
            return queryset.order_by(order_by)
        return queryset.order_by('id')


class PersonImportService:
    @staticmethod
    def import_dataframe(
        df: Any,
        column_mapping: dict[str, str],
        matching_fields: list[str],
        *,
        metadata_handler: MetadataHandler | None = None,
        max_cell_length: int = 255,
        max_metadata_length: int = 1000,
    ) -> PersonImportResult:
        errors: list[str] = []
        new_persons = 0
        updated_persons = 0
        extra_columns = [col for col in df.columns if col not in column_mapping.values()]

        with transaction.atomic():
            for index, row in df.iterrows():
                query: dict[str, str] = {}
                for field in matching_fields:
                    column = column_mapping.get(field)
                    value = row.get(column)
                    if column and value is not None and str(value) != 'nan':
                        query[field] = str(value).strip()[:100]

                if not query:
                    errors.append(f'Row {index + 2}: No data for duplicate check.')
                    continue

                existing = Person.objects.filter(**query)
                if existing.count() > 1:
                    errors.append(f'Row {index + 2}: Multiple persons found.')
                    continue

                person = existing.first()
                is_new_person = person is None
                person = person or Person()

                for field, column in column_mapping.items():
                    if column and column in row and row[column] is not None and str(row[column]) != 'nan':
                        setattr(person, field, str(row[column]).strip()[:max_cell_length])

                metadata = {
                    column_name: str(row[column_name])[:max_metadata_length]
                    for column_name in extra_columns
                    if row[column_name] is not None and str(row[column_name]) != 'nan'
                }

                if metadata_handler:
                    metadata_handler(person, metadata)
                else:
                    if metadata:
                        person.metadata.update(metadata)
                    person.save()

                if is_new_person:
                    new_persons += 1
                else:
                    updated_persons += 1

        return {
            'errors': errors,
            'new_persons': new_persons,
            'updated_persons': updated_persons,
            'extra_columns': extra_columns,
        }


def filter_sort_paginate_persons(
    request: HttpRequest,
    base_queryset: QuerySet,
    page_size: int = DEFAULT_PERSON_PAGE_SIZE,
) -> PersonListContext:
    return PersonFilterService.filter_sort_paginate(request, base_queryset, page_size)
