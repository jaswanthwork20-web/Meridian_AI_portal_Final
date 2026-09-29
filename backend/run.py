"""
Application Entrypoint CLI
Usage: python run.py [--port 8001] [--reload]
"""
import sys
import uvicorn
from app.config import HOST, PORT

if __name__ == "__main__":
    port = PORT
    reload = "--reload" in sys.argv
    for arg in sys.argv:
        if arg.startswith("--port="):
            port = int(arg.split("=")[1])
    print(f"Starting Meridian Enterprise Helpdesk on http://{HOST}:{port} (Reload: {reload})...")
    uvicorn.run("app.main:app", host=HOST, port=port, reload=reload)
