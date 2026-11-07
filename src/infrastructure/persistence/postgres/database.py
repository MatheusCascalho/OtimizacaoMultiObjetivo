from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy.engine import Engine

from api.settings import Settings


def create_engine(settings: Settings) -> Engine:
    return sqlalchemy_create_engine(settings.database_url, pool_pre_ping=True)
