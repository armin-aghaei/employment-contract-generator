"""Database client for PostgreSQL connection."""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as DBSession
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
from dotenv import load_dotenv
from .models import Base

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")

# Create engine
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    echo=False
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class DatabaseClient:
    """Database client for managing connections."""
    
    @staticmethod
    def create_tables():
        """Create all tables in the database."""
        Base.metadata.create_all(bind=engine)
    
    @staticmethod
    @contextmanager
    def get_session():
        """Get database session context manager."""
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def get_db() -> DBSession:
    """Dependency for FastAPI endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
