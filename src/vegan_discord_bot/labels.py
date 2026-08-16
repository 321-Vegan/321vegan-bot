from vegan_discord_bot.models import ProductState, ProductStatus


STATUS_LABELS = {
    ProductStatus.MAYBE_VEGAN: "Maybe vegan",
    ProductStatus.VEGAN: "🌱 Vegan",
    ProductStatus.NON_VEGAN: "❌ Non vegan",
    ProductStatus.NOT_FOUND: "Introuvable",
}

STATE_LABELS = {
    ProductState.CREATED: "À vérifier",
    ProductState.NEED_CONTACT: "À contacter",
    ProductState.WAITING_BRAND_REPLY: "Contacté",
    ProductState.WAITING_PUBLISH: "À publier",
    ProductState.PUBLISHED: "Publié",
}


def status_label(status: ProductStatus) -> str:
    return STATUS_LABELS[status]


def state_label(state: ProductState) -> str:
    return STATE_LABELS[state]
