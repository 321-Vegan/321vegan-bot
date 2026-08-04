import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
from pydantic import SecretStr

from vegan_discord_bot.api_client import VeganApiNotFoundError
from vegan_discord_bot.commands import (
    ProductValidationCommands,
    brand_response_embed,
)
from vegan_discord_bot.config import Settings
from vegan_discord_bot.models import NonVeganReason, ProductStatus


def command_context(api):
    settings = Settings(
        DISCORD_BOT_TOKEN=SecretStr("discord-token"),
        DISCORD_APPLICATION_ID=1,
        DISCORD_GUILD_ID=2,
        VEGAN_API_BASE_URL="https://api.test",
        VEGAN_API_EMAIL="bot@example.com",
        VEGAN_API_PASSWORD=SecretStr("password"),
        DISCORD_ALLOWED_CHANNEL_ID=1350813080476581918,
        DISCORD_REQUIRED_ROLE_ID=1350810248256159805,
    )
    command = ProductValidationCommands(settings=settings, api_client=api)
    interaction = SimpleNamespace(
        channel_id=1350813080476581918,
        user=SimpleNamespace(
            id=123,
            roles=[SimpleNamespace(id=1350810248256159805)],
        ),
        response=SimpleNamespace(
            send_message=AsyncMock(),
            defer=AsyncMock(),
        ),
        edit_original_response=AsyncMock(),
    )
    return command, interaction


class ProductValidationCommandsTestCase(unittest.IsolatedAsyncioTestCase):
    def test_screenshot_is_a_required_attachment_option(self):
        parameters = {
            parameter.name: parameter
            for parameter in ProductValidationCommands.validate_product.parameters
        }

        assert parameters["capture"].required is True
        assert parameters["capture"].type is discord.AppCommandOptionType.attachment
        assert "réponse de la marque" in parameters["capture"].description
        assert parameters["raison"].required is False
        assert {choice.value for choice in parameters["raison"].choices} == {
            reason.value for reason in NonVeganReason
        }

    async def test_non_vegan_result_requires_a_reason(self):
        api = SimpleNamespace(fetch_product=AsyncMock())
        command, interaction = command_context(api)

        await command.handle_validate_product(
            interaction,
            ean="0123456789012",
            proposed_status=ProductStatus.NON_VEGAN,
            capture=SimpleNamespace(url="https://cdn.discordapp.com/capture.png"),
            non_vegan_reason=None,
        )

        api.fetch_product.assert_not_called()
        interaction.response.defer.assert_not_called()
        response = interaction.response.send_message.await_args
        assert "obligatoire" in response.args[0]
        assert response.kwargs["ephemeral"] is True

    async def test_vegan_result_rejects_a_non_vegan_reason(self):
        api = SimpleNamespace(fetch_product=AsyncMock())
        command, interaction = command_context(api)

        await command.handle_validate_product(
            interaction,
            ean="0123456789012",
            proposed_status=ProductStatus.VEGAN,
            capture=SimpleNamespace(url="https://cdn.discordapp.com/capture.png"),
            non_vegan_reason=NonVeganReason.FLAVORS,
        )

        api.fetch_product.assert_not_called()
        interaction.response.defer.assert_not_called()
        response = interaction.response.send_message.await_args
        assert "Ne renseignez pas" in response.args[0]
        assert response.kwargs["ephemeral"] is True

    def test_screenshot_embed_references_discord_attachment_without_reading_it(self):
        capture = SimpleNamespace(
            url="https://cdn.discordapp.com/attachments/1/2/reponse.png",
            read=AsyncMock(),
        )

        embed = brand_response_embed(capture)

        assert embed.image.url == capture.url
        capture.read.assert_not_called()

    async def test_unknown_ean_does_not_create_confirmation_prompt(self):
        api = SimpleNamespace(
            fetch_product=AsyncMock(side_effect=VeganApiNotFoundError("missing"))
        )
        command, interaction = command_context(api)

        await command.handle_validate_product(
            interaction,
            ean="  0000000000000  ",
            proposed_status=ProductStatus.VEGAN,
            capture=SimpleNamespace(
                url="https://cdn.discordapp.com/attachments/1/2/reponse.png"
            ),
        )

        api.fetch_product.assert_awaited_once_with("0000000000000")
        interaction.response.defer.assert_awaited_once_with(thinking=True)
        interaction.edit_original_response.assert_awaited_once()
        kwargs = interaction.edit_original_response.await_args.kwargs
        assert "Aucun produit trouvé" in kwargs["content"]
        assert kwargs["view"] is None
