"""
Application runner script
Starts FastAPI + Automation Service together
"""

import uvicorn
import sys
import os
import threading
import time
import signal
import webbrowser


# -------------------------------------------------
# Add project root to Python path
# -------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from app.utils.config import settings


# -------------------------------------------------
# Automation Service Runner
# -------------------------------------------------
def start_automation():
    """
    Start the automation service in a background thread
    """
    try:
        from app.Automation.automation_service import main as automation_main
        print("[>|<] Starting Automation Service...")
        automation_main()
    except Exception as e:
        print(f"[X] Automation Service failed to start: {e}")


# -------------------------------------------------
# FastAPI Runner
# -------------------------------------------------
def start_api():
    """
    Start FastAPI (blocking)
    """
    print("=" * 60)
    print(f">>Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print("=" * 60)
    print(f">> Host: {settings.HOST}")
    print(f">>Port: {settings.PORT}")
    print(f"📚 Docs: http://{settings.HOST}:{settings.PORT}/docs")
    print(f"📊 Health: http://{settings.HOST}:{settings.PORT}/health")
    print("=" * 60)
    print()

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,  # IMPORTANT: keep False to avoid double automation
        log_level=settings.LOG_LEVEL.lower()
    )


# -------------------------------------------------
# Graceful Shutdown Handler
# -------------------------------------------------
def shutdown_handler(signum, frame):
    print("\n[>X<] Shutdown signal received. Stopping services...")
    sys.exit(0)


# -------------------------------------------------
# Main Entry Point
# -------------------------------------------------
def main():
    # Handle CTRL+C and termination
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Start automation in background thread
    automation_thread = threading.Thread(
        target=start_automation,
        daemon=True  # Dies automatically when main process exits
    )
    automation_thread.start()


    # Open browser after short delay
    threading.Timer(2.0, lambda: webbrowser.open("http://127.0.0.1:8000")).start()

    # Small delay so automation initializes cleanly
    time.sleep(1)

    # Start FastAPI (this blocks)
    start_api()


if __name__ == "__main__":
    main()
