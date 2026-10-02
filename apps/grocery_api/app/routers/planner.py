"""
Same-origin proxy to the separate Meal Planner (agent) service.

The agent runs in its own Python environment and process. This router validates
the browser's request, forwards it over HTTP with an explicit timeout, and
attaches links to product detail pages for the products the agent selected.

Endpoints are plain `def` (not `async def`) so FastAPI runs them in its thread
pool: the blocking HTTP call (which may include a slow model call) never blocks
the event loop. The agent calls back into /items/search on this same app while
a proxy request is in flight; the thread pool makes that safe.

No API keys are used or returned here; the agent holds its own.
"""

import json
import os
import urllib.error
import urllib.request
from decimal import Decimal
from typing import Any, Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.repository.manager import repo_manager

router = APIRouter()

Unit = Literal["g", "kg", "oz", "lb", "ml", "l", "count", "dozen"]
Planner = Literal["deterministic", "llm"]


def _service_url() -> str:
    return os.getenv("PLANNER_SERVICE_URL", "http://127.0.0.1:5001").rstrip(
        "/"
    )


def _timeout() -> float:
    return float(os.getenv("PLANNER_TIMEOUT_SECONDS", "60"))


class PantryItem(BaseModel):
    """One ingredient the user already has."""

    ingredient: str = Field(min_length=1, max_length=40)
    quantity: Decimal = Field(gt=0, le=10_000_000)
    unit: Unit


class PlanRequest(BaseModel):
    """Structured meal-plan request (form input)."""

    budget: Decimal = Field(gt=0, le=1_000_000)
    people: int = Field(ge=1, le=50)
    dietary_preferences: list[
        Literal["vegetarian", "vegan", "high_protein"]
    ] = Field(default_factory=list, max_length=3)
    pantry: list[PantryItem] = Field(default_factory=list, max_length=20)
    planner: Planner = "deterministic"


class ChatRequest(BaseModel):
    """One chat turn plus the conversation state collected so far."""

    message: str = Field(min_length=1, max_length=500)
    pending: Optional[dict[str, Any]] = None
    planner: Planner = "deterministic"


def _forward(path: str, payload: dict) -> dict:
    url = f"{_service_url()}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_timeout()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Meal planner service returned HTTP {e.code}.",
        ) from e
    except TimeoutError as e:
        raise HTTPException(
            status_code=504,
            detail=(
                "Meal planner service did not answer within "
                f"{_timeout():.0f}s."
            ),
        ) from e
    except (urllib.error.URLError, OSError) as e:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Meal planner service is not reachable at {_service_url()}. "
                "Start it (see the README), then try again."
            ),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=502,
            detail="Meal planner service returned an invalid response.",
        ) from e


def _attach_links(body: dict, db: Session) -> dict:
    """Add product_url to each selected line item whose product exists here.

    Only an internal detail page is linked: the data has no verified retailer
    URL, so retailer_url is always None (never built from a product ID).
    """
    result = body.get("result") if isinstance(body, dict) else None
    cost = result.get("cost") if isinstance(result, dict) else None
    if not isinstance(cost, dict):
        return body
    repo_manager.initialize(db)
    for li in cost.get("line_items") or []:
        li["retailer_url"] = None
        li["product_url"] = None
        pid, store = li.get("product_id"), li.get("store_id")
        if not isinstance(pid, str) or not isinstance(store, str):
            continue
        key = f"{store}:{pid}"
        item = repo_manager.get_item(key)
        if item and str(item["id"]) == pid:
            li["product_url"] = "/products/" + quote(key, safe=":")
    return body


@router.post("/plan")
def plan(req: PlanRequest, db: Session = Depends(get_db)):
    """Structured form input -> agent /plan."""
    payload = {
        "planner": req.planner,
        "request": {
            "budget": str(req.budget),
            "people": req.people,
            "dietary_preferences": req.dietary_preferences,
            "pantry": [
                {
                    "ingredient": p.ingredient.strip().lower(),
                    "quantity": str(p.quantity),
                    "unit": p.unit,
                }
                for p in req.pantry
            ],
        },
    }
    return _attach_links(_forward("/plan", payload), db)


@router.post("/chat")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    """One natural-language turn -> agent /chat (clarify or plan)."""
    payload = {
        "message": req.message,
        "pending": req.pending,
        "planner": req.planner,
    }
    return _attach_links(_forward("/chat", payload), db)
