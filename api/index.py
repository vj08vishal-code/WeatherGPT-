"""Vercel entrypoint for WeatherGPT FastAPI application."""
from backend.main import app

# Vercel expects a module-level ASGI application named app.
