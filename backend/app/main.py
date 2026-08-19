"""
Guardian AI — Main FastAPI Application
Context-Aware Autonomous Personal Safety & Mobility Anomaly Platform
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .db import init_db
from .routers import users, journeys, simulation, safety_checks, alerts, context, dashboard

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables on startup
    init_db()
    yield

app = FastAPI(
    title="Guardian AI API",
    description="Context-Aware Autonomous Personal Safety & Mobility Anomaly Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(users.router)
app.include_router(journeys.router)
app.include_router(simulation.router)
app.include_router(safety_checks.router)
app.include_router(alerts.router)
app.include_router(context.router)
app.include_router(dashboard.router)

@app.get("/")
def root():
    return {
        "app": "Guardian AI",
        "tagline": "Your journey doesn't need a panic button. Observe. Understand. Verify. Protect.",
        "status": "ONLINE",
        "docs_url": "/docs"
    }

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "guardian-ai-backend",
        "version": "1.0.0"
    }
