# WeatherGPT — Vercel deployment

This package is prepared to deploy the existing FastAPI + vanilla frontend as one Vercel project.

- `api/index.py` exposes the FastAPI app to Vercel Python Functions.
- `vercel.json` serves the frontend and `/static/*` assets.
- `requirements.txt` contains Python dependencies.
- `.env` is intentionally excluded.

Optional environment variable in Vercel:
- `OPENWEATHER_API_KEY` — enables OpenWeather as an additional verification provider. Without it, the app can use MET Norway as the secondary provider.
