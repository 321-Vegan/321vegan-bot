from collections.abc import Iterable


WRONG_CHANNEL_MESSAGE = (
    "Cette commande est autorisée uniquement dans le salon réponses-marques."
)
MISSING_ROLE_MESSAGE = (
    "Vous devez posséder le rôle Contributeurice pour utiliser cette commande."
)


def authorization_error(
    *,
    channel_id: int | None,
    role_ids: Iterable[int],
    allowed_channel_id: int,
    required_role_id: int,
) -> str | None:
    """Return a denial reason using Discord IDs only."""
    if channel_id != allowed_channel_id:
        return WRONG_CHANNEL_MESSAGE
    if required_role_id not in set(role_ids):
        return MISSING_ROLE_MESSAGE
    return None


def role_ids_from_user(user: object) -> list[int]:
    return [role.id for role in getattr(user, "roles", ()) if hasattr(role, "id")]
