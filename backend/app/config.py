from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    data_file: str = "data/courses.json"
    media_dir: str = "media"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
