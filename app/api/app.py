from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

api = FastAPI(title="Mood Analyzer API")

api.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://orange-swan-index.lovable.app",
        "https://id-preview--eae7594e-2204-4532-b499-d86c4c79210e.lovable.app",
        "https://orange-swan-index-web.vercel.app",
        "https://*.vercel.app",  # covers all vercel preview deployments too
    ],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

api.include_router(router)