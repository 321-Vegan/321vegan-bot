from vegan_discord_bot.labels import state_label, status_label
from vegan_discord_bot.models import (
    NonVeganReason,
    ProductResponse,
    ProductState,
    ProductStatus,
)


def product_name(product: ProductResponse) -> str:
    return product.name or "Produit sans nom"


def confirmation_message(
    preview: ProductResponse,
    proposed_status: ProductStatus,
    contributor_mention: str,
    non_vegan_reason: NonVeganReason | None = None,
) -> str:
    reason_line = (
        "Raison non végane : "
        f"**{non_vegan_reason.brand_response_description}**\n"
        if non_vegan_reason is not None
        else ""
    )
    return (
        "🔎 **Confirmation de validation produit**\n"
        f"Produit : **{product_name(preview)}**\n"
        f"EAN : `{preview.ean}`\n"
        f"Statut actuel : **{status_label(preview.status)}**\n"
        f"État actuel : **{state_label(preview.state)}**\n"
        f"Statut proposé : **{status_label(proposed_status)}**\n"
        f"{reason_line}"
        "État proposé : **À PUBLIER**\n"
        f"Contributeurice : {contributor_mention}\n\n"
        "Capture de la réponse de la marque : **affichée ci-dessous**\n"
        "_(Le bot ne télécharge ni ne transmet ce fichier.)_\n\n"
        "Confirmez-vous cette validation ?"
    )


def processing_message(
    preview: ProductResponse,
    proposed_status: ProductStatus,
    contributor_mention: str,
    non_vegan_reason: NonVeganReason | None = None,
) -> str:
    reason_line = (
        "\nRaison non végane : "
        f"**{non_vegan_reason.brand_response_description}**"
        if non_vegan_reason is not None
        else ""
    )
    return (
        "⏳ **Validation en cours — ne pas relancer immédiatement**\n"
        f"Produit : **{product_name(preview)}** (`{preview.ean}`)\n"
        f"Demande : **{status_label(preview.status)}** → "
        f"**{status_label(proposed_status)}**; "
        f"**{state_label(preview.state)}** → **À publier**\n"
        f"Contributeurice : {contributor_mention}"
        f"{reason_line}"
    )


def success_message(
    previous: ProductResponse,
    updated: ProductResponse,
    contributor_mention: str,
) -> str:
    reason_line = (
        f"\nRaison non végane : **{updated.problem_description}**"
        if (
            updated.status == ProductStatus.NON_VEGAN
            and updated.problem_description
        )
        else ""
    )
    return (
        f"✅ **Produit validé par {contributor_mention}**\n\n"
        f"Produit : **{product_name(updated)}**\n"
        f"EAN : `{updated.ean}`\n"
        f"Statut : **{status_label(previous.status)}** → "
        f"**{status_label(updated.status)}**\n"
        f"État : **{state_label(previous.state)}** → "
        f"**{state_label(updated.state)}**"
        f"{reason_line}"
    )


def cancelled_message(preview: ProductResponse, contributor_mention: str) -> str:
    return (
        "🚫 **Validation annulée**\n"
        f"Produit : **{product_name(preview)}** (`{preview.ean}`)\n"
        f"Contributeurice : {contributor_mention}\n"
        "Aucune modification n’a été envoyée à l’API."
    )


def expired_message(preview: ProductResponse) -> str:
    return (
        "⌛ **Confirmation expirée**\n"
        f"Produit : **{product_name(preview)}** (`{preview.ean}`)\n"
        "Aucune modification n’a été envoyée à l’API. Relancez la commande si nécessaire."
    )


def conflict_message(preview: ProductResponse, latest: ProductResponse) -> str:
    reason_change = (
        "Raison non végane aperçue : "
        f"**{preview.problem_description or 'Aucune'}**; "
        "raison actuelle : "
        f"**{latest.problem_description or 'Aucune'}**\n"
        if preview.problem_description != latest.problem_description
        else ""
    )
    return (
        "⚠️ **Validation interrompue : le produit a changé**\n"
        f"Produit : **{product_name(latest)}** (`{latest.ean}`)\n"
        f"Statut aperçu : **{status_label(preview.status)}**; "
        f"statut actuel : **{status_label(latest.status)}**\n"
        f"État aperçu : **{state_label(preview.state)}**; "
        f"état actuel : **{state_label(latest.state)}**\n"
        f"{reason_change}"
        "Aucune modification n’a été envoyée. Relancez `/valider-produit`."
    )


def no_op_message(
    product: ProductResponse,
    contributor_mention: str,
) -> str:
    reason_line = (
        f"\nRaison non végane : **{product.problem_description}**"
        if (
            product.status == ProductStatus.NON_VEGAN
            and product.problem_description
        )
        else ""
    )
    return (
        "ℹ️ **Aucune modification nécessaire**\n"
        f"Produit : **{product_name(product)}** (`{product.ean}`)\n"
        f"Contributeurice : {contributor_mention}\n"
        f"Le produit est déjà **{status_label(product.status)}** et "
        f"**{state_label(ProductState.WAITING_PUBLISH)}**."
        f"{reason_line}"
    )


def api_failure_message(
    preview: ProductResponse,
    contributor_mention: str,
    detail: str,
) -> str:
    return (
        "❌ **La validation n’a pas pu être terminée**\n"
        f"Produit : **{product_name(preview)}** (`{preview.ean}`)\n"
        f"Contributeurice : {contributor_mention}\n"
        f"Erreur : {detail[:400]}\n"
        "Vérifiez l’état du produit avant de réessayer."
    )


def partial_failure_message(
    preview: ProductResponse,
    contributor_mention: str,
    detail: str,
) -> str:
    return (
        "⚠️ **Validation partiellement terminée**\n"
        f"Produit : **{product_name(preview)}** (`{preview.ean}`)\n"
        f"Contributeurice : {contributor_mention}\n"
        "Une première étape a été enregistrée, mais le produit n’a pas pu "
        "être mis à jour.\n"
        f"Erreur : {detail[:400]}\n"
        "Relancez la commande : elle reprendra uniquement l’étape restante."
    )
