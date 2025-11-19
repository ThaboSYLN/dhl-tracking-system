"""
Application runner script
Provides easy startup and management commands
"""
import uvicorn
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.config import settings


def main():
    """Run the FastAPI application"""
    print("=" * 60)
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print("=" * 60)
    print(f"📍 Host: {settings.HOST}")
    print(f"📍 Port: {settings.PORT}")
    print(f"📚 Documentation: http://{settings.HOST}:{settings.PORT}/docs")
    print(f"📊 Health Check: http://{settings.HOST}:{settings.PORT}/health")
    print("=" * 60)
    print()
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )


def init_db():
    """Initialize database"""
    from app.utils.database import init_db
    print("🗄️  Initializing database...")
    init_db()
    print("✅ Database initialized successfully!")


def reset_db():
    """Reset database (CAUTION: Deletes all data)"""
    from app.utils.database import db_manager
    
    response = input("⚠️  WARNING: This will delete all data! Are you sure? (yes/no): ")
    if response.lower() == 'yes':
        print("🔄 Resetting database...")
        db_manager.reset_database()
        print("✅ Database reset successfully!")
    else:
        print("❌ Operation cancelled")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "init-db":
            init_db()
        elif command == "reset-db":
            reset_db()
        elif command == "run":
            main()
        else:
            print(f"Unknown command: {command}")
            print("Available commands: run, init-db, reset-db")
    else:
        main()

