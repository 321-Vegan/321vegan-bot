from types import SimpleNamespace

from vegan_discord_bot.authorization import (
    MISSING_ROLE_MESSAGE,
    WRONG_CHANNEL_MESSAGE,
    authorization_error,
    role_ids_from_user,
)


ALLOWED_CHANNEL = 1350813080476581918
REQUIRED_ROLE = 1350810248256159805


def test_correct_channel_and_role_are_authorized():
    assert (
        authorization_error(
            channel_id=ALLOWED_CHANNEL,
            role_ids=[REQUIRED_ROLE],
            allowed_channel_id=ALLOWED_CHANNEL,
            required_role_id=REQUIRED_ROLE,
        )
        is None
    )


def test_incorrect_channel_is_rejected():
    assert authorization_error(
        channel_id=42,
        role_ids=[REQUIRED_ROLE],
        allowed_channel_id=ALLOWED_CHANNEL,
        required_role_id=REQUIRED_ROLE,
    ) == WRONG_CHANNEL_MESSAGE


def test_missing_role_is_rejected():
    assert authorization_error(
        channel_id=ALLOWED_CHANNEL,
        role_ids=[999],
        allowed_channel_id=ALLOWED_CHANNEL,
        required_role_id=REQUIRED_ROLE,
    ) == MISSING_ROLE_MESSAGE


def test_role_authorization_never_uses_names():
    user = SimpleNamespace(
        roles=[
            SimpleNamespace(id=REQUIRED_ROLE, name="Renamed"),
            SimpleNamespace(id=999, name="Contributeurice"),
        ]
    )
    assert role_ids_from_user(user) == [REQUIRED_ROLE, 999]
