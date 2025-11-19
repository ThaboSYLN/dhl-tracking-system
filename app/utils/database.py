"""
Database connection and session management
Follows dependency injection pattern
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
from typing import Generator
import os

from app.utils.config import settings
from app.models.database import Base


# Create database engine
def get_engine():
    """
    Create and return SQLAlchemy engine
    Uses StaticPool for SQLite to handle threading
    """
    # Ensure data directory exists
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    # Create engine with appropriate settings
    if settings.DATABASE_URL.startswith("sqlite"):
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=settings.DEBUG
        )
    else:
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            echo=settings.DEBUG
        )
    
    return engine


# Create session factory
engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    Initialize database - create all tables
    Should be called on application startup
    """
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized successfully!")


def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection for database sessions
    Yields a database session and ensures proper cleanup
    
    Usage in FastAPI:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            # Use db here
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Context manager for database sessions
    Useful for background tasks and scripts
    
    Usage:
        with get_db_context() as db:
            # Use db here
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class DatabaseManager:
    """
    Database manager for administrative tasks
    Follows singleton pattern
    """
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def create_tables(self):
        """Create all tables"""
        Base.metadata.create_all(bind=self.engine)
    
    def drop_tables(self):
        """Drop all tables - USE WITH CAUTION"""
        Base.metadata.drop_all(bind=self.engine)
    
    def reset_database(self):
        """Reset database - drops and recreates all tables"""
        self.drop_tables()
        self.create_tables()
        print("🔄 Database reset successfully!")
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()


# Export database manager instance
db_manager = DatabaseManager()

