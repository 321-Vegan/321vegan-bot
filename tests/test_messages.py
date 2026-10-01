from datetime import datetime, timezone

from vegan_discord_bot.messages import confirmation_message, success_message
from vegan_discord_bot.models import (
    NonVeganReason,
    ProductResponse,
    ProductState,
    ProductStatus,
)


def product(*, status, state, problem_description=None, updated_at=None):
    return ProductResponse(
        id=1,
        ean="0123456789012",
        name="Biscuits",
        status=status,
        state=state,
        problem_description=problem_description,
        updated_at=updated_at or datetime.now(timezone.utc),
    )


def test_confirmation_uses_friendly_french_labels():
    preview = product(
        status=ProductStatus.MAYBE_VEGAN,
        state=ProductState.CREATED,
    )
    message = confirmation_message(preview, ProductStatus.VEGAN, "<@123>")
    assert "Biscuits" in message
    assert "0123456789012" in message
    assert "Maybe vegan" in message
    assert "À vérifier" in message
    assert "🌱 Vegan" in message
    assert "À PUBLIER" in message
    assert "<@123>" in message
    assert "Capture de la réponse de la marque" in message
    assert "affichée ci-dessous" in message
    assert "ne télécharge ni ne transmet" in message


def test_non_vegan_confirmation_contains_selected_brand_response_reason():
    preview = product(
        status=ProductStatus.MAYBE_VEGAN,
        state=ProductState.WAITING_BRAND_REPLY,
    )

    message = confirmation_message(
        preview,
        ProductStatus.NON_VEGAN,
        "<@123>",
        NonVeganReason.ANIMAL_PRODUCT_CLARIFICATION,
    )

    assert (
        "Clarifié avec des produits d'origine animale "
        "(réponse de la marque)"
    ) in message


def test_french_success_log_contains_before_and_authoritative_after_values():
    previous = product(
        status=ProductStatus.VEGAN,
        state=ProductState.PUBLISHED,
    )
    updated = product(
        status=ProductStatus.NON_VEGAN,
        state=ProductState.WAITING_PUBLISH,
        problem_description="Vitamine D d'origine animale (réponse de la marque)",
    )
    message = success_message(previous, updated, "<@123>")
    assert "Produit validé par <@123>" in message
    assert "🌱 Vegan** → **❌ Non vegan" in message
    assert "Publié** → **À publier" in message
    assert "0123456789012" in message
    assert "Vitamine D d'origine animale (réponse de la marque)" in message
