from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from src.bootstrap.config import settings
from src.db.base import Base

engine = create_engine(settings.app_database_url, echo=False, poolclass=NullPool)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    expire_on_commit=False,
)
