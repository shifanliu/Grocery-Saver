"""Curated, hand-reviewed data: meal templates and product package sizes.

Package sizes are kept separate from prices. Prices ALWAYS come from search
results; this file only says how much one package of a known product holds.

Package sizes were read by hand off the product names returned by the Grocery
Saver API (Costco Business Delivery rows scraped 2026-07-22). The API has no
size field, so there is no parser: a product that is not listed here is
"unsupported" by design.

Deliberately NOT mapped: items sold by weight whose listed price looks like a
per-lb price (e.g. "Chicken Breasts, 9 lb avg wt" listed at $2.99). Treating
that as the price of a 9 lb pack would be wrong, so they stay unsupported.

Dietary tags are hand-assigned from each template's ingredient list. They are
NOT allergen detection or medical advice: packaged products' own ingredient
lists (e.g. tortillas, pasta) were not checked.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Package:
    ingredient: str
    quantity: Decimal
    unit: str


def _p(ingredient: str, quantity: str, unit: str) -> Package:
    return Package(ingredient, Decimal(quantity), unit)


# product_id -> package. Order within an ingredient = "preferred first".
PACKAGES: dict[str, Package] = {
    # rice: 25 lb bags
    "841930": _p("rice", "25", "lb"),   # Kirkland Thai Hom Mali Jasmine, 25 lbs
    "207": _p("rice", "25", "lb"),      # Homai Calrose, 25 lbs
    "1831343": _p("rice", "25", "lb"),  # Supreme Parboiled, 25 lbs
    "5415": _p("rice", "25", "lb"),     # Bunge Homai Brown Rice, 25 lbs
    # beans: #10 cans, 6 lb 12 oz = 108 oz
    "171345": _p("beans", "108", "oz"),  # Teasdale Black Beans
    "405378": _p("beans", "108", "oz"),  # Teasdale Pinto Beans
    "3015": _p("beans", "108", "oz"),    # Teasdale Kidney Beans
    # canned tomatoes
    "1959935": _p("tomatoes", "102", "oz"),  # Prima Terra Whole Peeled, 102 oz
    "1977524": _p("tomatoes", "106", "oz"),  # Prima Terra Ground Peeled, 106 oz
    # onions: 10 lb bags
    "699753": _p("onion", "10", "lb"),  # Yellow Onions, 10 lbs
    "228233": _p("onion", "10", "lb"),  # Sweet Onion, 10 lbs
    # potatoes: 10 lb bags
    "5938": _p("potatoes", "10", "lb"),  # Gold Potatoes, 10 lbs
    "7445": _p("potatoes", "10", "lb"),  # Baking Potatoes, 10 lbs
    # eggs
    "1738408": _p("eggs", "2", "dozen"),  # Kirkland Large Eggs, 2 Dozen
    "1832329": _p("eggs", "40", "count"),  # Jumbo Eggs, Cage Free, 40 ct
    # tofu: 16 oz x 4
    "1204135": _p("tofu", "64", "oz"),
    # broccoli
    "5623": _p("broccoli", "3", "lb"),     # Broccoli Florets, 3 lbs
    "258966": _p("broccoli", "3.5", "lb"),  # Flav-R-Pac frozen, 3.5 lbs
    # carrots: 2 lb x 2
    "412": _p("carrots", "4", "lb"),
    # pasta: 10 lb x 2
    "1953370": _p("pasta", "20", "lb"),
    # tortillas
    "17351": _p("tortillas", "100", "count"),  # Guerrero 6" corn, 100 ct
    "576692": _p("tortillas", "60", "count"),  # La Fiesta 4.5" corn, 60 ct
    # canned chunk chicken: 12.5 oz x 6
    "51070": _p("chicken", "75", "oz"),
    # oats
    "446586": _p("oats", "10", "lb"),    # Quaker Old Fashioned Oatmeal, 10 lbs
    "731962": _p("oats", "112", "oz"),   # Bob's Red Mill Quick Cooking Oats, 112 oz
}

# What to search for, per ingredient (the API search is a substring match on
# the product name and is noisy; the PACKAGES mapping does the real filtering).
SEARCH_TERMS: dict[str, str] = {
    "rice": "rice",
    "beans": "beans",
    "tomatoes": "tomatoes",
    "onion": "onion",
    "potatoes": "potatoes",
    "eggs": "eggs",
    "tofu": "tofu",
    "broccoli": "broccoli",
    "carrots": "carrots",
    "pasta": "spaghetti",
    "tortillas": "tortillas",
    "chicken": "chicken breast",
    "oats": "oats",
}


# Rough protein per 100 g (as measured in the templates: dry/as purchased), or per
# piece for count items. Hand-entered from typical published food-composition values;
# approximate, for the "high_protein" tag and a displayed estimate only. NOT nutrition
# advice, and it ignores brand differences and cooking losses.
PROTEIN_G_PER_100G = {
    "chicken": Decimal("21"),   # canned chunk chicken, drained
    "tofu": Decimal("12"),      # firm
    "beans": Decimal("7"),      # canned, drained
    "rice": Decimal("7"),       # dry
    "oats": Decimal("13"),      # dry
    "pasta": Decimal("13"),     # dry
    "potatoes": Decimal("2"),
    "broccoli": Decimal("2.8"),
    "carrots": Decimal("0.9"),
    "tomatoes": Decimal("0.9"),
    "onion": Decimal("1.1"),
}
PROTEIN_G_PER_COUNT = {"eggs": Decimal("6"), "tortillas": Decimal("1.5")}
HIGH_PROTEIN_MIN_G = Decimal("30")  # estimated grams per serving for the high_protein tag


@dataclass(frozen=True)
class MealTemplate:
    id: str
    name: str
    tags: frozenset[str]  # subset of {"vegetarian", "vegan"}; empty = contains meat
    # ingredient -> (quantity per person, unit)
    per_person: tuple[tuple[str, Decimal, str], ...]

    @property
    def ingredients(self) -> list[str]:
        return [i for i, _, _ in self.per_person]

    @property
    def est_protein_g(self) -> Decimal:
        """Approximate protein per serving, from the hand-entered table above."""
        total = Decimal(0)
        for ing, qty, unit in self.per_person:
            if unit == "count":
                total += PROTEIN_G_PER_COUNT[ing] * qty
            else:
                total += PROTEIN_G_PER_100G[ing] * qty / 100
        return total.quantize(Decimal("1"))


def _t(id_, name, tags, *items) -> MealTemplate:
    return MealTemplate(
        id_, name, frozenset(tags),
        tuple((i, Decimal(q), u) for i, q, u in items),
    )


_VEGAN = ("vegan", "vegetarian")

TEMPLATES: tuple[MealTemplate, ...] = (
    _t("bean_rice_bowl", "Bean and rice bowl", _VEGAN,
       ("rice", "80", "g"), ("beans", "150", "g"),
       ("tomatoes", "60", "g"), ("onion", "40", "g")),
    _t("tofu_veggie_stirfry", "Tofu and vegetable stir-fry with rice", _VEGAN,
       ("tofu", "120", "g"), ("broccoli", "150", "g"), ("carrots", "60", "g"),
       ("rice", "80", "g"), ("onion", "30", "g")),
    _t("bean_tacos", "Bean tacos", _VEGAN,
       ("tortillas", "3", "count"), ("beans", "120", "g"),
       ("tomatoes", "50", "g"), ("onion", "30", "g")),
    _t("pasta_tomato", "Pasta with tomato sauce", _VEGAN,
       ("pasta", "100", "g"), ("tomatoes", "150", "g"), ("onion", "40", "g")),
    _t("egg_potato_hash", "Egg and potato hash", ("vegetarian",),
       ("eggs", "2", "count"), ("potatoes", "250", "g"), ("onion", "50", "g")),
    _t("chicken_rice_bowl", "Chicken and rice bowl", (),
       ("chicken", "85", "g"), ("rice", "80", "g"),
       ("broccoli", "100", "g"), ("carrots", "40", "g")),
)

_HP = "high_protein"
_FIT = (
    _t("chicken_broccoli_power_bowl", "Chicken, rice and broccoli power bowl", (_HP,),
       ("chicken", "150", "g"), ("rice", "90", "g"), ("broccoli", "150", "g")),
    _t("chicken_bean_chili", "Chicken and bean chili", (_HP,),
       ("chicken", "120", "g"), ("beans", "150", "g"),
       ("tomatoes", "150", "g"), ("onion", "40", "g")),
    _t("egg_veggie_scramble", "Egg and potato veggie scramble", ("vegetarian", _HP),
       ("eggs", "4", "count"), ("potatoes", "200", "g"),
       ("broccoli", "100", "g"), ("onion", "30", "g")),
    _t("savory_egg_oats", "Savory oats with eggs", ("vegetarian", _HP),
       ("oats", "80", "g"), ("eggs", "4", "count")),
    _t("tofu_rice_power_bowl", "Tofu, rice and vegetable power bowl", (*_VEGAN, _HP),
       ("tofu", "250", "g"), ("rice", "80", "g"),
       ("broccoli", "120", "g"), ("carrots", "50", "g")),
    _t("tofu_bean_scramble", "Tofu and bean scramble", (*_VEGAN, _HP),
       ("tofu", "200", "g"), ("beans", "100", "g"), ("potatoes", "150", "g"),
       ("tomatoes", "60", "g"), ("onion", "40", "g")),
)

TEMPLATES = TEMPLATES + _FIT

TEMPLATES_BY_ID = {t.id: t for t in TEMPLATES}


def eligible_templates(preferences: list[str]) -> list[MealTemplate]:
    """Templates carrying every requested tag (hand-assigned; not allergen detection).

    "high_protein" means the template's estimated protein per serving is at least
    HIGH_PROTEIN_MIN_G, using the rough table above."""
    wanted = set(preferences)
    return [t for t in TEMPLATES if wanted <= t.tags]
