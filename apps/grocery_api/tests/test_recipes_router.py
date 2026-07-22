"""
Tests for the /recipes router. The OpenAI-backed service is mocked so CI
never makes a real API call.
"""

from unittest.mock import patch

from app.services.recipes import (
    RecipeServiceConfigError,
    RecipeServiceUpstreamError,
)


def test_suggest_recipes_ok(client):
    fake_recipes = [
        {
            "title": "Honey Banana Toast",
            "uses_basket_items": ["Honey", "Banana"],
            "additional_ingredients": ["Bread"],
            "steps": ["Toast bread", "Top with banana and honey"],
        }
    ]
    with patch(
        "app.routers.recipes.recipes_service.suggest_recipes",
        return_value=fake_recipes,
    ):
        r = client.post("/recipes/suggest", json={"items": ["Honey", "Banana"]})
    assert r.status_code == 200
    body = r.json()
    assert body["recipes"] == fake_recipes
    assert "ts" in body


def test_suggest_recipes_empty_basket(client):
    r = client.post("/recipes/suggest", json={"items": []})
    assert r.status_code == 400


def test_suggest_recipes_missing_items_key(client):
    r = client.post("/recipes/suggest", json={})
    assert r.status_code == 400


def test_suggest_recipes_missing_api_key(client):
    with patch(
        "app.routers.recipes.recipes_service.suggest_recipes",
        side_effect=RecipeServiceConfigError("OPENAI_API_KEY is not configured."),
    ):
        r = client.post("/recipes/suggest", json={"items": ["Honey"]})
    assert r.status_code == 503


def test_suggest_recipes_upstream_error(client):
    with patch(
        "app.routers.recipes.recipes_service.suggest_recipes",
        side_effect=RecipeServiceUpstreamError("boom"),
    ):
        r = client.post("/recipes/suggest", json={"items": ["Honey"]})
    assert r.status_code == 503
