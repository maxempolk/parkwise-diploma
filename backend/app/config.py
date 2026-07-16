from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./app.db"
    admin_username: str = "admin"
    admin_password_hash: str = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
    jwt_secret: str = "development-secret-change-me-32-characters"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
