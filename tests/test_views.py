import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from vegan_discord_bot.api_client import VeganApiTimeoutError
from vegan_discord_bot.models import (
    NonVeganReason,
    ProductResponse,
    ProductState,
    ProductStatus,
)
from vegan_discord_bot.views import ValidationConfirmationView


BASE_TIME = datetime(2026, 8, 4, 9, 0, tzinfo=timezone.utc)


def product(
    *,
    status=ProductStatus.MAYBE_VEGAN,
    state=ProductState.WAITING_BRAND_REPLY,
    problem_description=None,
    updated_at=BASE_TIME,
):
    return ProductResponse(
        id=12,
        ean="0123456789012",
        name="Biscuits",
        status=status,
        state=state,
        problem_description=problem_description,
        updated_at=updated_at,
    )


def updated_product(status, problem_description=None):
    return product(
        status=status,
        state=ProductState.WAITING_PUBLISH,
        problem_description=problem_description,
        updated_at=BASE_TIME + timedelta(seconds=1),
    )


def interaction(*, user_id=123, interaction_id=999, message=None):
    return SimpleNamespace(
        id=interaction_id,
        user=SimpleNamespace(id=user_id),
        response=SimpleNamespace(
            send_message=AsyncMock(),
            edit_message=AsyncMock(),
        ),
        message=message or SimpleNamespace(edit=AsyncMock()),
    )


class ValidationConfirmationViewTestCase(unittest.IsolatedAsyncioTestCase):
    def make_view(self, api, preview, target, reason=None):
        return ValidationConfirmationView(
            api_client=api,
            preview=preview,
            proposed_status=target,
            invoker_id=123,
            contributor_mention="<@123>",
            non_vegan_reason=reason,
            retry_delay=0,
        )

    async def test_only_original_contributor_can_use_buttons(self):
        api = SimpleNamespace(
            fetch_product=AsyncMock(),
            update_product=AsyncMock(),
        )
        view = self.make_view(api, product(), ProductStatus.VEGAN)
        other = interaction(user_id=456)
        assert await view.interaction_check(other) is False
        other.response.send_message.assert_awaited_once()
        assert other.response.send_message.await_args.kwargs["ephemeral"] is True
        api.fetch_product.assert_not_called()
        api.update_product.assert_not_called()

    async def test_cancel_does_not_fetch_or_update(self):
        api = SimpleNamespace(
            fetch_product=AsyncMock(),
            update_product=AsyncMock(),
        )
        view = self.make_view(api, product(), ProductStatus.VEGAN)
        invoker = interaction()
        await view.handle_cancel(invoker)
        api.fetch_product.assert_not_called()
        api.update_product.assert_not_called()
        assert "Validation annulée" in (
            invoker.response.edit_message.await_args.kwargs["content"]
        )
        assert invoker.response.edit_message.await_args.kwargs["view"] is view
        assert all(child.disabled for child in view.children)

    async def test_expired_confirmation_does_not_update(self):
        api = SimpleNamespace(
            fetch_product=AsyncMock(),
            update_product=AsyncMock(),
        )
        view = self.make_view(api, product(), ProductStatus.VEGAN)
        view.message = SimpleNamespace(edit=AsyncMock())
        await view.on_timeout()
        api.fetch_product.assert_not_called()
        api.update_product.assert_not_called()
        assert "Confirmation expirée" in (
            view.message.edit.await_args.kwargs["content"]
        )
        assert view.message.edit.await_args.kwargs["view"] is view
        assert all(child.disabled for child in view.children)

    async def test_vegan_and_non_vegan_validations_and_corrections(self):
        cases = [
            (ProductStatus.MAYBE_VEGAN, ProductStatus.VEGAN),
            (ProductStatus.MAYBE_VEGAN, ProductStatus.NON_VEGAN),
            (ProductStatus.VEGAN, ProductStatus.NON_VEGAN),
            (ProductStatus.NON_VEGAN, ProductStatus.VEGAN),
        ]
        for index, (before, target) in enumerate(cases):
            with self.subTest(before=before, target=target):
                preview = product(status=before)
                api = SimpleNamespace(
                    fetch_product=AsyncMock(return_value=preview),
                    update_product=AsyncMock(return_value=updated_product(target)),
                )
                view = self.make_view(api, preview, target)
                invoker = interaction(interaction_id=1000 + index)
                await view.handle_confirm(invoker)
                api.fetch_product.assert_awaited_once_with("0123456789012")
                api.update_product.assert_awaited_once_with(
                    product_id=12,
                    ean="0123456789012",
                    status=target,
                )
                final = invoker.message.edit.await_args.kwargs["content"]
                assert "Produit validé" in final
                assert "À publier" in final

    async def test_same_status_with_different_state_still_updates(self):
        preview = product(
            status=ProductStatus.VEGAN,
            state=ProductState.PUBLISHED,
        )
        api = SimpleNamespace(
            fetch_product=AsyncMock(return_value=preview),
            update_product=AsyncMock(
                return_value=updated_product(ProductStatus.VEGAN)
            ),
        )
        view = self.make_view(api, preview, ProductStatus.VEGAN)
        await view.handle_confirm(interaction())
        api.update_product.assert_awaited_once()

    async def test_non_vegan_reason_replaces_problem_description(self):
        preview = product(problem_description="Ancienne raison")
        reason = NonVeganReason.NATURAL_FLAVORS
        expected_description = "ARÔMES NATURELS (réponse de la marque)"
        api = SimpleNamespace(
            fetch_product=AsyncMock(return_value=preview),
            update_product=AsyncMock(
                return_value=updated_product(
                    ProductStatus.NON_VEGAN,
                    problem_description=expected_description,
                )
            ),
        )
        invoker = interaction()
        view = self.make_view(api, preview, ProductStatus.NON_VEGAN, reason)

        await view.handle_confirm(invoker)

        api.update_product.assert_awaited_once_with(
            product_id=12,
            ean="0123456789012",
            status=ProductStatus.NON_VEGAN,
            problem_description=expected_description,
        )
        assert expected_description in (
            invoker.message.edit.await_args.kwargs["content"]
        )

    async def test_different_non_vegan_reason_is_not_treated_as_no_op(self):
        preview = product(
            status=ProductStatus.NON_VEGAN,
            state=ProductState.WAITING_PUBLISH,
            problem_description="ARÔMES (réponse de la marque)",
        )
        reason = NonVeganReason.VITAMIN_D
        expected_description = "VITAMINE D (réponse de la marque)"
        api = SimpleNamespace(
            fetch_product=AsyncMock(return_value=preview),
            update_product=AsyncMock(
                return_value=updated_product(
                    ProductStatus.NON_VEGAN,
                    problem_description=expected_description,
                )
            ),
        )
        view = self.make_view(api, preview, ProductStatus.NON_VEGAN, reason)

        await view.handle_confirm(interaction())

        api.update_product.assert_awaited_once_with(
            product_id=12,
            ean="0123456789012",
            status=ProductStatus.NON_VEGAN,
            problem_description=expected_description,
        )

    async def test_complete_no_op_avoids_put(self):
        preview = product(
            status=ProductStatus.VEGAN,
            state=ProductState.WAITING_PUBLISH,
        )
        api = SimpleNamespace(
            fetch_product=AsyncMock(return_value=preview),
            update_product=AsyncMock(),
        )
        invoker = interaction()
        view = self.make_view(api, preview, ProductStatus.VEGAN)
        await view.handle_confirm(invoker)
        api.update_product.assert_not_called()
        assert "Aucune modification nécessaire" in (
            invoker.message.edit.await_args.kwargs["content"]
        )

    async def test_changed_product_is_rejected_before_put(self):
        preview = product()
        latest = product(updated_at=BASE_TIME + timedelta(seconds=1))
        api = SimpleNamespace(
            fetch_product=AsyncMock(return_value=latest),
            update_product=AsyncMock(),
        )
        invoker = interaction()
        view = self.make_view(api, preview, ProductStatus.VEGAN)
        await view.handle_confirm(invoker)
        api.update_product.assert_not_called()
        content = invoker.message.edit.await_args.kwargs["content"]
        assert "le produit a changé" in content
        assert "Relancez `/valider-produit`" in content

    async def test_double_click_is_processed_only_once(self):
        preview = product()
        api = SimpleNamespace(
            fetch_product=AsyncMock(return_value=preview),
            update_product=AsyncMock(
                return_value=updated_product(ProductStatus.VEGAN)
            ),
        )
        view = self.make_view(api, preview, ProductStatus.VEGAN)
        first = interaction(interaction_id=1)
        second = interaction(interaction_id=2)
        await view.handle_confirm(first)
        await view.handle_confirm(second)
        api.fetch_product.assert_awaited_once()
        api.update_product.assert_awaited_once()
        second.response.send_message.assert_awaited_once()

    async def test_api_timeout_edits_public_message_without_internal_detail(self):
        preview = product()
        api = SimpleNamespace(
            fetch_product=AsyncMock(
                side_effect=VeganApiTimeoutError("L’API n’a pas répondu à temps.")
            ),
            update_product=AsyncMock(),
        )
        invoker = interaction()
        view = self.make_view(api, preview, ProductStatus.VEGAN)
        await view.handle_confirm(invoker)
        api.update_product.assert_not_called()
        content = invoker.message.edit.await_args.kwargs["content"]
        assert "validation n’a pas pu être terminée" in content
        assert "n’a pas répondu à temps" in content

    async def test_successful_update_retries_discord_message_edit(self):
        preview = product(status=ProductStatus.VEGAN)
        api = SimpleNamespace(
            fetch_product=AsyncMock(return_value=preview),
            update_product=AsyncMock(
                return_value=updated_product(ProductStatus.NON_VEGAN)
            ),
        )
        message = SimpleNamespace(
            edit=AsyncMock(side_effect=[RuntimeError("transient"), None])
        )
        view = self.make_view(api, preview, ProductStatus.NON_VEGAN)
        await view.handle_confirm(interaction(message=message))
        assert message.edit.await_count == 2


if __name__ == "__main__":
    unittest.main()
