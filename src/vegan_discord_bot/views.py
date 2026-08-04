import asyncio
import logging

import discord

from vegan_discord_bot.api_client import VeganApiClient, VeganApiError
from vegan_discord_bot.messages import (
    api_failure_message,
    cancelled_message,
    conflict_message,
    expired_message,
    no_op_message,
    processing_message,
    success_message,
)
from vegan_discord_bot.models import (
    NonVeganReason,
    ProductResponse,
    ProductState,
    ProductStatus,
)


log = logging.getLogger(__name__)


def product_changed(preview: ProductResponse, latest: ProductResponse) -> bool:
    return (
        preview.status != latest.status
        or preview.state != latest.state
        or preview.problem_description != latest.problem_description
        or preview.updated_at != latest.updated_at
    )


async def edit_message_with_retry(
    message: discord.Message,
    *,
    content: str,
    view: discord.ui.View | None,
    attempts: int,
    retry_delay: float,
) -> None:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            await message.edit(content=content, view=view)
            return
        except Exception as error:
            last_error = error
            if attempt + 1 < attempts:
                await asyncio.sleep(retry_delay)
    assert last_error is not None
    raise last_error


class ValidationConfirmationView(discord.ui.View):
    def __init__(
        self,
        *,
        api_client: VeganApiClient,
        preview: ProductResponse,
        proposed_status: ProductStatus,
        invoker_id: int,
        contributor_mention: str,
        non_vegan_reason: NonVeganReason | None = None,
        timeout: float = 180,
        retry_delay: float = 0.5,
    ) -> None:
        super().__init__(timeout=timeout)
        self.api_client = api_client
        self.preview = preview
        self.proposed_status = proposed_status
        self.invoker_id = invoker_id
        self.contributor_mention = contributor_mention
        self.non_vegan_reason = non_vegan_reason
        self.problem_description = (
            non_vegan_reason.brand_response_description
            if non_vegan_reason is not None
            else None
        )
        self.retry_delay = retry_delay
        self.message: discord.Message | None = None
        self._operation_lock = asyncio.Lock()
        self._finished = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.invoker_id:
            return True
        await interaction.response.send_message(
            "Seule la personne ayant lancé la commande peut utiliser ces boutons.",
            ephemeral=True,
        )
        return False

    def _disable_buttons(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    async def _already_finished(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "Cette confirmation est déjà terminée ou en cours de traitement.",
            ephemeral=True,
        )

    async def handle_confirm(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.invoker_id:
            await self.interaction_check(interaction)
            return

        async with self._operation_lock:
            if self._finished:
                await self._already_finished(interaction)
                return
            self._finished = True
            self._disable_buttons()
            try:
                await interaction.response.edit_message(
                    content=processing_message(
                        self.preview,
                        self.proposed_status,
                        self.contributor_mention,
                        self.non_vegan_reason,
                    ),
                    view=self,
                )
            except Exception:
                log.exception(
                    "Could not publish processing state; product update was not called"
                )
                self.stop()
                return

        message = interaction.message or self.message
        try:
            latest = await self.api_client.fetch_product(self.preview.ean)
            if product_changed(self.preview, latest):
                await self._edit_final_safely(
                    message,
                    content=conflict_message(self.preview, latest),
                    operation="publish stale-product conflict",
                )
                self.stop()
                return

            if (
                latest.status == self.proposed_status
                and latest.state == ProductState.WAITING_PUBLISH
                and (
                    self.problem_description is None
                    or latest.problem_description == self.problem_description
                )
            ):
                await self._edit_final_safely(
                    message,
                    content=no_op_message(latest, self.contributor_mention),
                    operation="publish no-op result",
                )
                self.stop()
                return

            update_kwargs = dict(
                product_id=latest.id,
                ean=latest.ean,
                status=self.proposed_status,
            )
            if self.problem_description is not None:
                update_kwargs["problem_description"] = self.problem_description
            updated = await self.api_client.update_product(**update_kwargs)
        except VeganApiError as error:
            await self._edit_final_safely(
                message,
                content=api_failure_message(
                    self.preview,
                    self.contributor_mention,
                    error.message,
                ),
                operation="publish API error",
            )
            self.stop()
            return
        except Exception:
            log.exception("Unexpected product-validation failure")
            await self._edit_final_safely(
                message,
                content=api_failure_message(
                    self.preview,
                    self.contributor_mention,
                    "Erreur interne inattendue.",
                ),
                operation="publish unexpected error",
            )
            self.stop()
            return

        try:
            await self._edit_final(
                message,
                content=success_message(latest, updated, self.contributor_mention),
                attempts=2,
            )
        except Exception:
            log.exception(
                "Product update succeeded but final Discord message edit failed twice",
                extra={"product_id": updated.id, "ean": updated.ean},
            )
        self.stop()

    async def handle_cancel(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.invoker_id:
            await self.interaction_check(interaction)
            return
        async with self._operation_lock:
            if self._finished:
                await self._already_finished(interaction)
                return
            self._finished = True
            self._disable_buttons()
            await interaction.response.edit_message(
                content=cancelled_message(
                    self.preview,
                    self.contributor_mention,
                ),
                view=self,
            )
            self.stop()

    async def _edit_final(
        self,
        message: discord.Message | None,
        *,
        content: str,
        attempts: int,
    ) -> None:
        if message is None:
            log.error("Cannot edit final Discord log: original message unavailable")
            return
        await edit_message_with_retry(
            message,
            content=content,
            view=None,
            attempts=attempts,
            retry_delay=self.retry_delay,
        )

    async def _edit_final_safely(
        self,
        message: discord.Message | None,
        *,
        content: str,
        operation: str,
    ) -> None:
        try:
            await self._edit_final(message, content=content, attempts=1)
        except Exception:
            log.exception("Could not %s on Discord", operation)

    @discord.ui.button(
        label="Confirmer",
        style=discord.ButtonStyle.success,
        custom_id="321vegan:product-validation:confirm",
    )
    async def confirm_button(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        await self.handle_confirm(interaction)

    @discord.ui.button(
        label="Annuler",
        style=discord.ButtonStyle.secondary,
        custom_id="321vegan:product-validation:cancel",
    )
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        await self.handle_cancel(interaction)

    async def on_timeout(self) -> None:
        async with self._operation_lock:
            if self._finished:
                return
            self._finished = True
            self._disable_buttons()
            if self.message is not None:
                try:
                    await self.message.edit(
                        content=expired_message(self.preview),
                        view=self,
                    )
                except Exception:
                    log.exception("Could not mark confirmation as expired")
            self.stop()
