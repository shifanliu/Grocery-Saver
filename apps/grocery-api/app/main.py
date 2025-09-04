"""
Main entry point for the Grocery API.

This module creates the FastAPI application, registers routers for items
and stores, and exposes the root endpoint.
"""

from fastapi import FastAPI

# Routers for API endpoints
from app.routers import items, stores

app = FastAPI(title="Grocery API")

# Register routers
app.include_router(items.router, prefix="/items", tags=["items"])
app.include_router(stores.router, prefix="/stores", tags=["stores"])


@app.get("/")
def root():
    """
    Root endpoint for the Grocery API.

    Returns:
        dict: A welcome message for API consumers.
    """
    return {"message": "Welcome to Grocery Saver API"}
