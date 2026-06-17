from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import models, transaction

from safedelete.config import FIELD_NAME
from safedelete.managers import (
    SafeDeleteAllManager as DjangoSafeDeleteAllManager,
    SafeDeleteDeletedManager as DjangoSafeDeleteDeletedManager,
    SafeDeleteManager as DjangoSafeDeleteManager,
)
from safedelete.models import SafeDeleteModel
from safedelete.queryset import SafeDeleteQueryset


class SafeDeleteQuerySet(SafeDeleteQueryset):
    def update(self, **kwargs):
        if FIELD_NAME in kwargs and kwargs[FIELD_NAME] is None:
            raise ValidationError(
                "Direct restore via queryset.update() is not allowed; use undelete()."
            )
        return super().update(**kwargs)


class SafeDeleteManager(DjangoSafeDeleteManager):
    _queryset_class = SafeDeleteQuerySet


class SafeDeleteAllManager(DjangoSafeDeleteAllManager):
    _queryset_class = SafeDeleteQuerySet


class SafeDeleteDeletedManager(DjangoSafeDeleteDeletedManager):
    _queryset_class = SafeDeleteQuerySet


class BaseSafeDeleteModel(SafeDeleteModel):
    objects = SafeDeleteManager()
    all_objects = SafeDeleteAllManager()
    deleted_objects = SafeDeleteDeletedManager()

    class Meta:
        abstract = True

    _restore_dependency_fields_cache = None
    _original_deleted_value = None
    _performing_restore = False

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._original_deleted_value = getattr(instance, FIELD_NAME, None)
        return instance

    @classmethod
    def get_restore_dependency_fields(cls):
        cached_fields = cls._restore_dependency_fields_cache
        if cached_fields is not None:
            return cached_fields

        dependency_fields = []
        for field in cls._meta.concrete_fields:
            if not isinstance(field, (models.ForeignKey, models.OneToOneField)):
                continue
            if getattr(field.remote_field, "parent_link", False):
                continue

            related_model = field.related_model
            if not isinstance(related_model, type):
                continue
            if not issubclass(related_model, SafeDeleteModel):
                continue

            dependency_fields.append(field)

        cls._restore_dependency_fields_cache = tuple(dependency_fields)
        return cls._restore_dependency_fields_cache

    def get_blocking_restore_fields(self):
        dependency_fields = self.get_restore_dependency_fields()
        if not dependency_fields:
            return []

        related_ids_by_model = defaultdict(set)
        fields_by_model = defaultdict(list)

        for field in dependency_fields:
            related_id = getattr(self, field.attname, None)
            if related_id is None:
                continue

            related_model = field.related_model
            related_ids_by_model[related_model].add(related_id)
            fields_by_model[related_model].append((field, related_id))

        if not related_ids_by_model:
            return []

        blocked_fields = []
        for related_model, related_ids in related_ids_by_model.items():
            deleted_ids = set(
                related_model.all_objects.filter(pk__in=related_ids)
                .exclude(**{FIELD_NAME: None})
                .values_list("pk", flat=True)
            )
            if not deleted_ids:
                continue

            for field, related_id in fields_by_model[related_model]:
                if related_id in deleted_ids:
                    blocked_fields.append(field)

        return blocked_fields

    def validate_restore_dependencies(self):
        blocked_fields = self.get_blocking_restore_fields()
        if not blocked_fields:
            return

        blocked_names = ", ".join(
            str(field.verbose_name or field.name) for field in blocked_fields
        )
        raise ValidationError(
            f"امکان بازیابی وجود ندارد؛ آبجکت‌های والد مرتبط هنوز حذف شده‌اند: {blocked_names}."
        )

    def save(self, keep_deleted=False, **kwargs):
        if (
            not self._performing_restore
            and not keep_deleted
            and not self._state.adding
            and self.pk is not None
            and self._was_deleted_before_save()
        ):
            keep_deleted = True

        result = super().save(keep_deleted=keep_deleted, **kwargs)
        self._original_deleted_value = getattr(self, FIELD_NAME, None)
        return result

    def undelete(self, force_policy=None, **kwargs):
        with transaction.atomic():
            self.validate_restore_dependencies()
            self._performing_restore = True
            try:
                result = super().undelete(force_policy=force_policy, **kwargs)
            finally:
                self._performing_restore = False
            self._original_deleted_value = getattr(self, FIELD_NAME, None)
            return result

    def _was_deleted_before_save(self):
        original_deleted = getattr(self, "_original_deleted_value", None)
        if original_deleted is not None:
            return True

        return type(self).all_objects.filter(pk=self.pk).exclude(
            **{FIELD_NAME: None}
        ).exists()
