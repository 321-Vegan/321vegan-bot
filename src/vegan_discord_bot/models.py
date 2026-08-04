from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ProductStatus(StrEnum):
    VEGAN = "VEGAN"
    NON_VEGAN = "NON_VEGAN"
    MAYBE_VEGAN = "MAYBE_VEGAN"
    NOT_FOUND = "NOT_FOUND"


class NonVeganReason(StrEnum):
    FLAVORS = "ARÔMES"
    NATURAL_FLAVORS = "ARÔMES NATURELS"
    VITAMIN_D = "VITAMINE D"
    ANIMAL_PRODUCT_CLARIFICATION = (
        "CLARIFIÉ AVEC DES PRODUITS D'ORIGINE ANIMALE"
    )

    @property
    def brand_response_description(self) -> str:
        return f"{self.value} (réponse de la marque)"


class ProductState(StrEnum):
    CREATED = "CREATED"
    NEED_CONTACT = "NEED_CONTACT"
    WAITING_BRAND_REPLY = "WAITING_BRAND_REPLY"
    WAITING_PUBLISH = "WAITING_PUBLISH"
    PUBLISHED = "PUBLISHED"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class ProductResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    ean: str
    name: str | None = None
    status: ProductStatus
    state: ProductState
    problem_description: str | None = None
    updated_at: datetime
