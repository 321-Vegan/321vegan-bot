import logging

import discord
from discord.ext import commands

from vegan_discord_bot.api_client import VeganApiClient
from vegan_discord_bot.commands import ProductValidationCommands
from vegan_discord_bot.config import Settings


log = logging.getLogger(__name__)


class VeganDiscordBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            application_id=settings.DISCORD_APPLICATION_ID,
        )
        self.settings = settings
        self.api_client = VeganApiClient(
            base_url=settings.VEGAN_API_BASE_URL,
            email=settings.VEGAN_API_EMAIL,
            password=settings.VEGAN_API_PASSWORD.get_secret_value(),
        )

    async def setup_hook(self) -> None:
        await self.add_cog(
            ProductValidationCommands(
                settings=self.settings,
                api_client=self.api_client,
            )
        )
        if not self.settings.DISCORD_SYNC_COMMANDS:
            log.info("Discord command synchronization is disabled")
            return

        if self.settings.DISCORD_GUILD_ID is not None:
            guild = discord.Object(id=self.settings.DISCORD_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synchronized %d development-guild command(s)", len(synced))
        else:
            synced = await self.tree.sync()
            log.info("Synchronized %d global command(s)", len(synced))

    async def close(self) -> None:
        await self.api_client.aclose()
        await super().close()


def create_bot(settings: Settings) -> VeganDiscordBot:
    return VeganDiscordBot(settings)
