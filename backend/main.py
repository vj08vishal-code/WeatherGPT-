"""
main.py - FastAPI Application Entrypoint for WeatherGPT.
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_DIR, HOST, PORT
from .api.routes import router as api_router

# Initialize FastAPI application
app = FastAPI(
    title="WeatherGPT",
    description="Production-quality conversational weather intelligence MVP for SIH",
    version="1.0.0"
)

# Enable CORS for development & cross-origin frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router)

# Mount frontend directory for static assets
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def serve_index():
    """Serves the main single-page ChatGPT-style interface."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "WeatherGPT API is active. Frontend index.html not found."}


@app.get("/style.css")
async def serve_css():
    """Direct root fallback for stylesheet."""
    css_path = FRONTEND_DIR / "style.css"
    if css_path.exists():
        return FileResponse(css_path, media_type="text/css")
    return FileResponse(FRONTEND_DIR / "style.css")


@app.get("/app.js")
async def serve_js():
    """Direct root fallback for script."""
    js_path = FRONTEND_DIR / "app.js"
    if js_path.exists():
        return FileResponse(js_path, media_type="application/javascript")
    return FileResponse(FRONTEND_DIR / "app.js")


if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Starting WeatherGPT on http://{HOST}:{PORT}")
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)
