import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pydantic import SecretStr

from vegan_discord_bot.__main__ import sync_commands_once
from vegan_discord_bot.config import Settings


class SyncCommandsTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_sync_forces_one_shot_sync_and_closes_the_bot(self):
        settings = Settings(
            DISCORD_BOT_TOKEN=SecretStr("discord-token"),
            DISCORD_APPLICATION_ID=1,
            DISCORD_GUILD_ID=2,
            DISCORD_SYNC_COMMANDS=False,
            VEGAN_API_BASE_URL="https://api.test",
            VEGAN_API_EMAIL="bot@example.com",
            VEGAN_API_PASSWORD=SecretStr("password"),
        )
        bot = SimpleNamespace(login=AsyncMock(), close=AsyncMock())

        with patch(
            "vegan_discord_bot.__main__.create_bot",
            return_value=bot,
        ) as create_bot:
            await sync_commands_once(settings)

        sync_settings = create_bot.call_args.args[0]
        assert settings.DISCORD_SYNC_COMMANDS is False
        assert sync_settings.DISCORD_SYNC_COMMANDS is True
        bot.login.assert_awaited_once_with("discord-token")
        bot.close.assert_awaited_once_with()

    async def test_sync_closes_the_bot_when_login_fails(self):
        settings = Settings(
            DISCORD_BOT_TOKEN=SecretStr("discord-token"),
            DISCORD_APPLICATION_ID=1,
            DISCORD_GUILD_ID=2,
            VEGAN_API_BASE_URL="https://api.test",
            VEGAN_API_EMAIL="bot@example.com",
            VEGAN_API_PASSWORD=SecretStr("password"),
        )
        bot = SimpleNamespace(
            login=AsyncMock(side_effect=RuntimeError("login failed")),
            close=AsyncMock(),
        )

        with patch(
            "vegan_discord_bot.__main__.create_bot",
            return_value=bot,
        ):
            with self.assertRaises(RuntimeError):
                await sync_commands_once(settings)

        bot.close.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
