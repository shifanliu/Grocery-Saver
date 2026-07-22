"""
LLM-backed recipe suggestion service.

Given a list of item names from a user's basket, asks an OpenAI model for
a handful of recipe ideas that primarily use those items.
"""

import json
import os
from typing import Any, Dict, List

from openai import APIError, OpenAI

MODEL = "gpt-4o-mini"

RECIPE_SCHEMA = {
    "name": "recipe_suggestions",
    "schema": {
        "type": "object",
        "properties": {
            "recipes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "uses_basket_items": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "additional_ingredients": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "steps": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "title",
                        "uses_basket_items",
                        "additional_ingredients",
                        "steps",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["recipes"],
        "additionalProperties": False,
    },
    "strict": True,
}


class RecipeServiceError(Exception):
    """Base error for recipe suggestion failures."""


class RecipeServiceConfigError(RecipeServiceError):
    """Raised when the service is not configured (e.g. no API key)."""


class RecipeServiceUpstreamError(RecipeServiceError):
    """Raised when the OpenAI API call itself fails."""


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sk-REPLACE_ME":
        raise RecipeServiceConfigError("OPENAI_API_KEY is not configured.")
    return OpenAI(api_key=api_key)


def suggest_recipes(item_names: List[str]) -> List[Dict[str, Any]]:
    """Ask the LLM for recipe ideas built around the given basket items."""
    client = _get_client()

    prompt = (
        "A shopper has these grocery items in their basket:\n"
        f"{', '.join(item_names)}\n\n"
        "Suggest 3 simple recipes that primarily use these items. For each "
        "recipe, list which of the basket items it uses, any additional "
        "common ingredients needed, and short numbered steps."
    )

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={
                "type": "json_schema",
                "json_schema": RECIPE_SCHEMA,
            },
        )
    except APIError as e:
        raise RecipeServiceUpstreamError(str(e)) from e

    content = response.choices[0].message.content
    return json.loads(content)["recipes"]
