from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="READY_SET_WASH_", env_file=".env", extra="ignore")
    mode: Literal["demo", "live"] = "demo"
    product_code: str = ""
    tariff_code: str = ""
    octopus_api_key: SecretStr = SecretStr("")

    @model_validator(mode="after")
    def validate_live(self) -> "Settings":
        if self.mode == "live" and (not self.product_code or not self.tariff_code):
            raise ValueError("Live mode requires product and tariff codes")
        return self
