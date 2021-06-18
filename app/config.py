from pydantic import BaseSettings


class Settings(BaseSettings):
    db_url: str
    db_username: str
    db_password: str
    db_schema_name: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int = 365 * 10 * 24 * 30

    class Config:
        env_file = '.env'


settings = Settings()
