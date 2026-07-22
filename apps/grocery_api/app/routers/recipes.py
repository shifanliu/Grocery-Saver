"""
Router for LLM-backed recipe suggestions based on a user's basket.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.services import recipes as recipes_service

router = APIRouter()


@router.post("/suggest")
def suggest_recipes(payload: dict):
    """
    Suggest recipes based on a list of basket item names.
    """
    items = payload.get("items", [])
    if not isinstance(items, list) or not items:
        raise HTTPException(
            status_code=400,
            detail="items must be a non-empty list of item names",
        )

    try:
        recipes = recipes_service.suggest_recipes(items)
    except recipes_service.RecipeServiceError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    return {
        "recipes": recipes,
        "ts": datetime.utcnow().isoformat(),
    }
