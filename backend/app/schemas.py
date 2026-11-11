from pydantic import BaseModel, Field, field_validator

class AssetCreate(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    creator: str = Field(min_length=2, max_length=150)
    sha256: str
    license_text: str = Field(min_length=4, max_length=2000)
    price_cents: int = Field(ge=100, le=1000000)
    @field_validator('sha256')
    @classmethod
    def valid_sha256(cls, v):
        if len(v) != 64 or any(c not in '0123456789abcdefABCDEF' for c in v):
            raise ValueError('Must be a 64-character SHA-256 hex digest')
        return v.lower()

class OrderCreate(BaseModel):
    asset_id: str

class HashCheck(BaseModel):
    sha256: str = Field(min_length=64, max_length=64)
