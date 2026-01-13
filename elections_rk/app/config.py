from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")
    
    database_url: str = "postgresql://postgres:postgres@localhost:5432/elections_rk"


settings = Settings()
