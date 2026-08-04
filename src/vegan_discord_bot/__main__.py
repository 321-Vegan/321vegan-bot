import argparse
import asyncio
import logging

from vegan_discord_bot.bot import create_bot
from vegan_discord_bot.config import Settings, get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="321Vegan Discord bot")
    parser.add_argument(
        "--sync-commands",
        action="store_true",
        help="Synchronize Discord commands once, then exit.",
    )
    return parser.parse_args()


async def sync_commands_once(settings: Settings) -> None:
    sync_settings = settings.model_copy(
        update={"DISCORD_SYNC_COMMANDS": True}
    )
    bot = create_bot(sync_settings)
    try:
        await bot.login(sync_settings.DISCORD_BOT_TOKEN.get_secret_value())
    finally:
        await bot.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = parse_args()
    settings = get_settings()
    if args.sync_commands:
        asyncio.run(sync_commands_once(settings))
        return

    bot = create_bot(settings)
    bot.run(settings.DISCORD_BOT_TOKEN.get_secret_value())


if __name__ == "__main__":
    main()
