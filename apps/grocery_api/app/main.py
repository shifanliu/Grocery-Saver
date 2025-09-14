# flake8: noqa: E402
"""
Main entry point for the Grocery Saver API and UI.

This module creates the FastAPI application, registers routers for items
and stores, serves static files, and renders Jinja2 templates for UI pages.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import SessionLocal
from app.repository.manager import repo_manager
from app.routers import items, stores

load_dotenv()

# Base directory: apps/grocery_api/app
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Grocery API")

# Register API routers
app.include_router(items.router, prefix="/items", tags=["items"])
app.include_router(stores.router, prefix="/stores", tags=["stores"])

print("DATABASE_URL =", os.getenv("DATABASE_URL"))
print("REPO_TYPE =", os.getenv("REPO_TYPE"))

# Mount static files
app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)

# Jinja2 templates
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
def ui_home(
    request: Request,
    q: str | None = Query(None, description="Search query"),
    store_id: str | None = Query(None, description="Filter by store"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=50, description="Items per page"),
):
    """
    UI home page with search, pagination, and store filter.
    """
    offset = (page - 1) * limit

    with SessionLocal() as db:
        repo_manager.initialize(db)

        # Get stores for dropdown
        store_list = repo_manager.list_stores()

        # Get items
        if q:
            item_list = repo_manager.search_items(q, store_id)
        else:
            item_list = repo_manager.list_items(
                store_id=store_id,
                limit=limit,
                offset=offset,
                sort="last_seen_time",
                order="desc",
            )

        # Get stats
        stats = repo_manager.get_stats()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "items": item_list,
            "query": q,
            "store_id": store_id,
            "stores": store_list,
            "page": page,
            "limit": limit,
            "stats": stats,
        },
    )
