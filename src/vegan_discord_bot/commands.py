import logging

import discord
from discord import app_commands
from discord.ext import commands

from vegan_discord_bot.api_client import (
    VeganApiClient,
    VeganApiError,
    VeganApiNotFoundError,
)
from vegan_discord_bot.authorization import authorization_error, role_ids_from_user
from vegan_discord_bot.config import Settings
from vegan_discord_bot.messages import confirmation_message
from vegan_discord_bot.models import NonVeganReason, ProductStatus
from vegan_discord_bot.views import ValidationConfirmationView


log = logging.getLogger(__name__)


def brand_response_embed(capture: discord.Attachment) -> discord.Embed:
    embed = discord.Embed(title="Capture de la réponse de la marque")
    embed.set_image(url=capture.url)
    return embed


class ProductValidationCommands(commands.Cog):
    def __init__(
        self,
        *,
        settings: Settings,
        api_client: VeganApiClient,
    ) -> None:
        self.settings = settings
        self.api_client = api_client

    @app_commands.command(
        name="valider-produit",
        description="Valider ou corriger le statut végane d’un produit.",
    )
    @app_commands.describe(
        ean="Code EAN du produit",
        resultat="Résultat de la validation",
        capture="Capture d’écran de la réponse de la marque (obligatoire)",
        raison="Raison requise uniquement pour un résultat non-vegan",
    )
    @app_commands.choices(
        resultat=[
            app_commands.Choice(name="vegan", value="VEGAN"),
            app_commands.Choice(name="non-vegan", value="NON_VEGAN"),
        ],
        raison=[
            app_commands.Choice(name=reason.value, value=reason.value)
            for reason in NonVeganReason
        ],
    )
    async def validate_product(
        self,
        interaction: discord.Interaction,
        ean: str,
        resultat: app_commands.Choice[str],
        capture: discord.Attachment,
        raison: app_commands.Choice[str] | None = None,
    ) -> None:
        await self.handle_validate_product(
            interaction,
            ean=ean,
            proposed_status=ProductStatus(resultat.value),
            capture=capture,
            non_vegan_reason=(
                NonVeganReason(raison.value) if raison is not None else None
            ),
        )

    async def handle_validate_product(
        self,
        interaction: discord.Interaction,
        *,
        ean: str,
        proposed_status: ProductStatus,
        capture: discord.Attachment,
        non_vegan_reason: NonVeganReason | None = None,
    ) -> None:
        denial = authorization_error(
            channel_id=interaction.channel_id,
            role_ids=role_ids_from_user(interaction.user),
            allowed_channel_id=self.settings.DISCORD_ALLOWED_CHANNEL_ID,
            required_role_id=self.settings.DISCORD_REQUIRED_ROLE_ID,
        )
        if denial is not None:
            await interaction.response.send_message(denial, ephemeral=True)
            return

        normalized_ean = ean.strip()
        if not normalized_ean:
            await interaction.response.send_message(
                "L’EAN ne peut pas être vide.",
                ephemeral=True,
            )
            return

        if (
            proposed_status == ProductStatus.NON_VEGAN
            and non_vegan_reason is None
        ):
            await interaction.response.send_message(
                "La raison non végane est obligatoire lorsque le résultat "
                "est `non-vegan`.",
                ephemeral=True,
            )
            return
        if (
            proposed_status != ProductStatus.NON_VEGAN
            and non_vegan_reason is not None
        ):
            await interaction.response.send_message(
                "Ne renseignez pas de raison non végane lorsque le résultat "
                "est `vegan`.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)
        try:
            preview = await self.api_client.fetch_product(normalized_ean)
        except VeganApiNotFoundError:
            await interaction.edit_original_response(
                content=f"❌ Aucun produit trouvé pour l’EAN `{normalized_ean}`.",
                view=None,
            )
            return
        except VeganApiError as error:
            await interaction.edit_original_response(
                content=f"❌ Impossible de charger le produit : {error.message}",
                view=None,
            )
            return
        except Exception:
            log.exception("Unexpected product-preview failure")
            await interaction.edit_original_response(
                content="❌ Erreur interne inattendue pendant la recherche du produit.",
                view=None,
            )
            return

        if not preview.checkings:
            await interaction.edit_original_response(
                content=(
                    "❌ Impossible de valider l’EAN "
                    f"`{normalized_ean}` : aucune demande liée n’a été trouvée. "
                    "Aucune modification n’a été envoyée."
                ),
                view=None,
            )
            return

        contributor_mention = f"<@{interaction.user.id}>"
        view = ValidationConfirmationView(
            api_client=self.api_client,
            preview=preview,
            proposed_status=proposed_status,
            invoker_id=interaction.user.id,
            contributor_mention=contributor_mention,
            capture=capture,
            non_vegan_reason=non_vegan_reason,
        )
        message = await interaction.edit_original_response(
            content=confirmation_message(
                preview,
                proposed_status,
                contributor_mention,
                non_vegan_reason,
            ),
            embed=brand_response_embed(capture),
            view=view,
        )
        view.message = message
