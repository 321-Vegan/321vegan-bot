import asyncio
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from vegan_discord_bot.models import (
    ProductResponse,
    ProductState,
    ProductStatus,
    TokenResponse,
)


class VeganApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class VeganApiAuthenticationError(VeganApiError):
    pass


class VeganApiNotFoundError(VeganApiError):
    pass


class VeganApiTimeoutError(VeganApiError):
    pass


class VeganApiClient:
    """Async contributor client with in-memory bearer-token reuse."""

    def __init__(
        self,
        *,
        base_url: str,
        email: str,
        password: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._email = email
        self._password = password
        self._access_token: str | None = None
        self._authentication_lock = asyncio.Lock()
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=15.0, pool=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def authenticate(self) -> None:
        await self._authenticate(force=True)

    async def fetch_product(self, ean: str) -> ProductResponse:
        normalized_ean = ean.strip()
        if not normalized_ean:
            raise VeganApiError("L’EAN ne peut pas être vide.")
        response = await self._authenticated_request(
            "GET",
            f"/products/ean/{quote(normalized_ean, safe='')}",
        )
        return self._parse_product(response)

    async def update_product(
        self,
        *,
        product_id: int,
        ean: str,
        status: ProductStatus,
        problem_description: str | None = None,
    ) -> ProductResponse:
        payload = {
            "ean": ean,
            "status": status.value,
            "state": ProductState.WAITING_PUBLISH.value,
        }
        if problem_description is not None:
            payload["problem_description"] = problem_description
        response = await self._authenticated_request(
            "PUT",
            f"/products/{product_id}",
            json=payload,
        )
        return self._parse_product(response)

    async def _authenticate(
        self,
        *,
        force: bool,
        stale_token: str | None = None,
    ) -> str:
        async with self._authentication_lock:
            if not force and self._access_token is not None:
                return self._access_token
            if (
                force
                and stale_token is not None
                and self._access_token is not None
                and self._access_token != stale_token
            ):
                return self._access_token

            response = await self._raw_request(
                "POST",
                "/auth/login",
                data={"username": self._email, "password": self._password},
            )
            if response.is_error:
                self._access_token = None
                raise VeganApiAuthenticationError(
                    "Connexion du compte contributeurice du bot refusée.",
                    response.status_code,
                )
            try:
                token = TokenResponse.model_validate(response.json())
            except (ValueError, ValidationError) as error:
                self._access_token = None
                raise VeganApiAuthenticationError(
                    "Réponse d’authentification invalide reçue de l’API."
                ) from error
            self._access_token = token.access_token
            return token.access_token

    async def _authenticated_request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        token = await self._authenticate(force=False)
        response = await self._raw_request(
            method,
            url,
            headers={"Authorization": f"Bearer {token}"},
            **kwargs,
        )
        if response.status_code == 401:
            token = await self._authenticate(force=True, stale_token=token)
            response = await self._raw_request(
                method,
                url,
                headers={"Authorization": f"Bearer {token}"},
                **kwargs,
            )
        if response.is_error:
            self._raise_response_error(response)
        return response

    async def _raw_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        try:
            return await self._client.request(method, url, **kwargs)
        except httpx.TimeoutException as error:
            raise VeganApiTimeoutError(
                "L’API 321Vegan n’a pas répondu à temps."
            ) from error
        except httpx.RequestError as error:
            raise VeganApiError(
                "L’API 321Vegan est momentanément indisponible."
            ) from error

    @staticmethod
    def _raise_response_error(response: httpx.Response) -> None:
        if response.status_code == 404:
            raise VeganApiNotFoundError("Produit introuvable.", 404)
        if response.status_code == 401:
            raise VeganApiAuthenticationError(
                "La session API du bot a été refusée après reconnexion.",
                401,
            )
        raise VeganApiError(
            f"L’API 321Vegan a retourné une erreur HTTP {response.status_code}.",
            response.status_code,
        )

    @staticmethod
    def _parse_product(response: httpx.Response) -> ProductResponse:
        try:
            return ProductResponse.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            raise VeganApiError(
                "Réponse produit invalide reçue de l’API."
            ) from error

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
