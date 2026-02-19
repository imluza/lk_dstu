import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Settings(BaseModel):
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://cabinet:cabinet@localhost:5432/cabinet"
    )
    JWT_SECRET: str = os.getenv("JWT_SECRET", "devsecret")
    JWT_ALG: str = os.getenv("JWT_ALG", "HS256")
    ACCESS_TOKEN_EXPIRES_MIN: int = int(os.getenv("ACCESS_TOKEN_EXPIRES_MIN", "120"))

    MEDIA_ROOT: str = os.getenv("MEDIA_ROOT", os.path.join(BASE_DIR, "media"))
    MEDIA_URL: str = os.getenv("MEDIA_URL", "/media/")

settings = Settings()
