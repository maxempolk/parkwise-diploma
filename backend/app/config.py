from secrets import token_urlsafe

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./app.db"
    admin_username: str = "admin"
    admin_password_hash: str = "pbkdf2_sha256$600000$X4rX3LR-CS5Nix5Y_7JMOg$_7-11K3GKHgLt0wRuHAHlE8WdYwPsFihCxNI_lGAj9s"
    jwt_secret: str = Field(default_factory=lambda: token_urlsafe(32))

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
