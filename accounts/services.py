from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

User = get_user_model()


class UserService:
    @staticmethod
    def create_user(
        username: str,
        password: str,
        email: str = '',
        first_name: str = '',
        last_name: str = '',
        is_active: bool = True,
    ) -> tuple[User | None, str | None]:
        if not username or not password:
            return None, 'Username and password are required.'

        try:
            validate_password(password)
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=is_active,
            )
            return user, None
        except ValidationError as exc:
            return None, f"Invalid password: {' '.join(exc.messages)}"
        except IntegrityError:
            return None, 'Username or Email already exists.'
        except Exception as exc:
            return None, f'Error: {exc}'

    @staticmethod
    def update_user(
        user: User,
        username: str,
        email: str = '',
        first_name: str = '',
        last_name: str = '',
        password: str | None = None,
        is_active: bool = True,
    ) -> str | None:
        if not username:
            return 'Username is required.'

        try:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.is_active = is_active
            if password:
                validate_password(password, user)
                user.set_password(password)
            user.save()
            return None
        except ValidationError as exc:
            return f"Invalid password: {' '.join(exc.messages)}"
        except IntegrityError:
            return 'Username or Email already exists.'
        except Exception as exc:
            return f'Error: {exc}'

    @staticmethod
    def change_password(user: User, new_password: str, confirm_password: str) -> str | None:
        if not new_password or not confirm_password:
            return 'All fields are required.'
        if new_password != confirm_password:
            return 'Passwords do not match.'

        try:
            validate_password(new_password, user)
            user.set_password(new_password)
            user.save()
            return None
        except ValidationError as exc:
            return f'Invalid password: {" ".join(exc.messages)}'
        except Exception as exc:
            return f'Error: {exc}'

    @staticmethod
    def toggle_user_status(user: User, current_user: User) -> tuple[bool, str | None]:
        if user == current_user:
            return False, 'You cannot disable your own account.'
        if user.is_superuser:
            return False, 'Cannot disable superuser.'

        user.is_active = not user.is_active
        user.save()
        return True, None

    @staticmethod
    def assign_roles(user: User, role_ids: list[int], current_user: User) -> str | None:
        if user == current_user:
            return 'You cannot change your own roles.'

        try:
            user.groups.clear()
            if role_ids:
                user.groups.set(Group.objects.filter(pk__in=role_ids))
            return None
        except Exception as exc:
            return f'Error: {exc}'

    @staticmethod
    def get_logged_in_user_ids() -> set[int]:
        active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
        logged_in_user_ids: set[int] = set()
        for session in active_sessions:
            session_data = session.get_decoded()
            user_id = session_data.get('_auth_user_id')
            if user_id:
                logged_in_user_ids.add(int(user_id))
        return logged_in_user_ids
