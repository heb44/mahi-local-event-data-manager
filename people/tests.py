from django.test import TestCase

from people.models import Person
from people.services import PersonImportService


class PersonImportServiceTests(TestCase):
    def test_import_dataframe_creates_person_and_maps_metadata(self):
        class FakeDataFrame:
            columns = ['name_col', 'last_name_col', 'extra']

            def iterrows(self):
                yield 0, {'name_col': 'Ali', 'last_name_col': 'Rezaei', 'extra': 'value'}

        result = PersonImportService.import_dataframe(
            FakeDataFrame(),
            {'name': 'name_col', 'last_name': 'last_name_col'},
            ['name', 'last_name'],
        )

        self.assertEqual(result['errors'], [])
        self.assertEqual(result['new_persons'], 1)
        person = Person.objects.get()
        self.assertEqual(person.name, 'Ali')
        self.assertEqual(person.last_name, 'Rezaei')
        self.assertEqual(person.metadata['extra'], 'value')

    def test_import_dataframe_updates_existing_person(self):
        Person.objects.create(name='Ali', last_name='Rezaei')

        class FakeDataFrame:
            columns = ['name_col', 'last_name_col', 'phone_col']

            def iterrows(self):
                yield 0, {'name_col': 'Ali', 'last_name_col': 'Rezaei', 'phone_col': '123'}

        result = PersonImportService.import_dataframe(
            FakeDataFrame(),
            {'name': 'name_col', 'last_name': 'last_name_col', 'phone_number': 'phone_col'},
            ['name', 'last_name'],
        )

        self.assertEqual(result['updated_persons'], 1)
        person = Person.objects.get()
        self.assertEqual(person.phone_number, '123')
