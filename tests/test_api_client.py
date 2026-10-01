import json
import unittest
from urllib.parse import parse_qs

import httpx

from vegan_discord_bot.api_client import (
    VeganApiAuthenticationError,
    VeganApiClient,
    VeganApiError,
    VeganApiNotFoundError,
    VeganApiTimeoutError,
)
from vegan_discord_bot.models import ProductStatus


def product_json(
    *,
    ean="0123456789012",
    status="MAYBE_VEGAN",
    state="WAITING_BRAND_REPLY",
):
    return {
        "id": 12,
        "created_at": "2026-08-04T08:00:00+00:00",
        "updated_at": "2026-08-04T09:00:00+00:00",
        "ean": ean,
        "name": "Biscuits",
        "status": status,
        "state": state,
        "biodynamic": False,
        "created_from_off": False,
        "checkings": [],
    }


class VeganApiClientTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_authentication_format_token_reuse_and_leading_zero_ean(self):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path == "/auth/login":
                return httpx.Response(
                    200,
                    json={"access_token": "token-one", "token_type": "bearer"},
                )
            assert request.headers["Authorization"] == "Bearer token-one"
            return httpx.Response(200, json=product_json())

        http_client = httpx.AsyncClient(
            base_url="https://api.test",
            transport=httpx.MockTransport(handler),
        )
        client = VeganApiClient(
            base_url="https://ignored.test",
            email="bot@example.com",
            password="dedicated-password",
            http_client=http_client,
        )
        try:
            first = await client.fetch_product("  0123456789012  ")
            second = await client.fetch_product("0123456789012")
        finally:
            await http_client.aclose()

        assert first.ean == second.ean == "0123456789012"
        login_requests = [r for r in requests if r.url.path == "/auth/login"]
        assert len(login_requests) == 1
        login = login_requests[0]
        assert login.headers["Content-Type"].startswith(
            "application/x-www-form-urlencoded"
        )
        assert parse_qs(login.content.decode()) == {
            "username": ["bot@example.com"],
            "password": ["dedicated-password"],
        }
        product_requests = [r for r in requests if "/products/ean/" in r.url.path]
        assert len(product_requests) == 2
        assert product_requests[0].url.path.endswith("/0123456789012")

    async def test_401_reauthenticates_and_retries_original_request_once(self):
        login_count = 0
        product_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal login_count, product_count
            if request.url.path == "/auth/login":
                login_count += 1
                return httpx.Response(
                    200,
                    json={
                        "access_token": f"token-{login_count}",
                        "token_type": "bearer",
                    },
                )
            product_count += 1
            if request.headers["Authorization"] == "Bearer token-1":
                return httpx.Response(401)
            assert request.headers["Authorization"] == "Bearer token-2"
            return httpx.Response(200, json=product_json())

        http_client = httpx.AsyncClient(
            base_url="https://api.test",
            transport=httpx.MockTransport(handler),
        )
        client = VeganApiClient(
            base_url="https://ignored.test",
            email="bot@example.com",
            password="password",
            http_client=http_client,
        )
        try:
            await client.fetch_product("0123456789012")
        finally:
            await http_client.aclose()

        assert login_count == 2
        assert product_count == 2

    async def test_second_401_is_not_retried_forever(self):
        counts = {"login": 0, "product": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/auth/login":
                counts["login"] += 1
                return httpx.Response(
                    200,
                    json={"access_token": "token", "token_type": "bearer"},
                )
            counts["product"] += 1
            return httpx.Response(401)

        http_client = httpx.AsyncClient(
            base_url="https://api.test",
            transport=httpx.MockTransport(handler),
        )
        client = VeganApiClient(
            base_url="https://ignored.test",
            email="bot@example.com",
            password="password",
            http_client=http_client,
        )
        try:
            with self.assertRaises(VeganApiAuthenticationError):
                await client.fetch_product("0123456789012")
        finally:
            await http_client.aclose()

        assert counts == {"login": 2, "product": 2}

    async def test_unknown_ean_is_mapped_to_not_found(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/auth/login":
                return httpx.Response(
                    200,
                    json={"access_token": "token", "token_type": "bearer"},
                )
            return httpx.Response(404)

        http_client = httpx.AsyncClient(
            base_url="https://api.test",
            transport=httpx.MockTransport(handler),
        )
        client = VeganApiClient(
            base_url="https://ignored.test",
            email="bot@example.com",
            password="password",
            http_client=http_client,
        )
        try:
            with self.assertRaises(VeganApiNotFoundError):
                await client.fetch_product("0000000000000")
        finally:
            await http_client.aclose()

    async def test_put_contains_only_allowed_product_fields_and_no_checking_calls(self):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path == "/auth/login":
                return httpx.Response(
                    200,
                    json={"access_token": "token", "token_type": "bearer"},
                )
            return httpx.Response(
                200,
                json=product_json(status="NON_VEGAN", state="WAITING_PUBLISH"),
            )

        http_client = httpx.AsyncClient(
            base_url="https://api.test",
            transport=httpx.MockTransport(handler),
        )
        client = VeganApiClient(
            base_url="https://ignored.test",
            email="bot@example.com",
            password="password",
            http_client=http_client,
        )
        try:
            updated = await client.update_product(
                product_id=12,
                ean="0123456789012",
                status=ProductStatus.NON_VEGAN,
                problem_description="Arômes (réponse de la marque)",
            )
        finally:
            await http_client.aclose()

        put = next(r for r in requests if r.method == "PUT")
        assert put.url.path == "/products/12"
        assert json.loads(put.content) == {
            "ean": "0123456789012",
            "status": "NON_VEGAN",
            "state": "WAITING_PUBLISH",
            "problem_description": "Arômes (réponse de la marque)",
        }
        assert updated.status == ProductStatus.NON_VEGAN
        assert all("checking" not in r.url.path.lower() for r in requests)

    async def test_vegan_update_leaves_problem_description_untouched(self):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path == "/auth/login":
                return httpx.Response(
                    200,
                    json={"access_token": "token", "token_type": "bearer"},
                )
            return httpx.Response(
                200,
                json=product_json(status="VEGAN", state="WAITING_PUBLISH"),
            )

        http_client = httpx.AsyncClient(
            base_url="https://api.test",
            transport=httpx.MockTransport(handler),
        )
        client = VeganApiClient(
            base_url="https://ignored.test",
            email="bot@example.com",
            password="password",
            http_client=http_client,
        )
        try:
            await client.update_product(
                product_id=12,
                ean="0123456789012",
                status=ProductStatus.VEGAN,
            )
        finally:
            await http_client.aclose()

        put = next(r for r in requests if r.method == "PUT")
        assert "problem_description" not in json.loads(put.content)

    async def test_api_timeout_is_sanitized(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/auth/login":
                return httpx.Response(
                    200,
                    json={"access_token": "token", "token_type": "bearer"},
                )
            raise httpx.ReadTimeout("private network detail", request=request)

        http_client = httpx.AsyncClient(
            base_url="https://api.test",
            transport=httpx.MockTransport(handler),
        )
        client = VeganApiClient(
            base_url="https://ignored.test",
            email="bot@example.com",
            password="password",
            http_client=http_client,
        )
        try:
            with self.assertRaises(VeganApiTimeoutError) as context:
                await client.fetch_product("0123456789012")
        finally:
            await http_client.aclose()

        assert "n’a pas répondu à temps" in context.exception.message
        assert "private network detail" not in context.exception.message

    async def test_unavailable_api_error_is_sanitized(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/auth/login":
                return httpx.Response(
                    200,
                    json={"access_token": "token", "token_type": "bearer"},
                )
            raise httpx.ConnectError("private host detail", request=request)

        http_client = httpx.AsyncClient(
            base_url="https://api.test",
            transport=httpx.MockTransport(handler),
        )
        client = VeganApiClient(
            base_url="https://ignored.test",
            email="bot@example.com",
            password="password",
            http_client=http_client,
        )
        try:
            with self.assertRaises(VeganApiError) as context:
                await client.fetch_product("0123456789012")
        finally:
            await http_client.aclose()

        assert "momentanément indisponible" in context.exception.message
        assert "private host detail" not in context.exception.message
