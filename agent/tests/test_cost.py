"""Criterion 2 (and the unit-incompatibility part of 4): compute_cost."""
from decimal import Decimal as D

from mealplan import catalog
from mealplan.catalog import Package
from mealplan.tools import compute_cost


def prod(pid, price, name="x"):
    return {"product_id": pid, "name": name, "price": None if price is None else D(price),
            "store_id": "S", "last_seen_time": "2026-07-22T00:00:00Z", "category": "c",
            "active": True}


PKGS = {  # synthetic package sizes, independent of the real catalog
    "R": Package("rice", D("1000"), "g"),
    "B": Package("beans", D("1000"), "g"),
    "T": Package("tomatoes", D("1000"), "g"),
    "O": Package("onion", D("100"), "g"),
    "P": Package("pasta", D("1000"), "g"),
}
SEL = {"rice": prod("R", "10.00"), "beans": prod("B", "3.00"),
       "tomatoes": prod("T", "2.00"), "onion": prod("O", "1.00"),
       "pasta": prod("P", "4.00")}


def line(res, ing):
    return next(li for li in res["line_items"] if li["ingredient"] == ing)


def test_whole_package_rounding():
    # bean_rice_bowl: rice 80 g/person. 13 people = 1040 g -> 2 packs of 1000 g
    res = compute_cost(["bean_rice_bowl"], SEL, 13, [], PKGS)
    assert line(res, "rice")["packages_needed"] == 2
    # exactly 1000 g (12.5 people is not valid; use 25 people at 40 g -> onion 1000g/100g)
    res = compute_cost(["bean_rice_bowl"], SEL, 25, [], PKGS)
    assert line(res, "onion")["packages_needed"] == 10  # exactly divisible: no extra pack


def test_scaling_with_people():
    two = compute_cost(["bean_rice_bowl"], SEL, 2, [], PKGS)
    four = compute_cost(["bean_rice_bowl"], SEL, 4, [], PKGS)
    assert line(two, "rice")["required"] == D("160")
    assert line(four, "rice")["required"] == D("320")
    assert line(four, "beans")["required"] == D("600")


def test_pantry_deduction_compatible_units():
    pantry = [{"ingredient": "rice", "quantity": D("1"), "unit": "lb"}]  # 453.59237 g
    res = compute_cost(["bean_rice_bowl"], SEL, 2, pantry, PKGS)
    li = line(res, "rice")
    assert li["pantry_deducted"] == D("160")      # capped at what is required
    assert li["packages_needed"] == 0 and li["line_total"] == D("0")
    pantry = [{"ingredient": "rice", "quantity": D("100"), "unit": "g"}]
    res = compute_cost(["bean_rice_bowl"], SEL, 14, pantry, PKGS)  # 1120 g - 100 g = 1020
    assert line(res, "rice")["remaining"] == D("1020")
    assert line(res, "rice")["packages_needed"] == 2


def test_pantry_incompatible_units_not_deducted():
    pantry = [{"ingredient": "rice", "quantity": D("5"), "unit": "l"}]
    res = compute_cost(["bean_rice_bowl"], SEL, 2, pantry, PKGS)
    li = line(res, "rice")
    assert li["pantry_deducted"] == D("0") and li["packages_needed"] == 1
    assert any("not compatible" in n for n in res["pantry_notes"])


def test_aggregation_happens_before_rounding():
    # onion: 40 g/person in both meals. 1 person: 40 + 40 = 80 g -> ONE 100 g pack.
    # (rounding each meal first would wrongly give 2 packs.)
    res = compute_cost(["bean_rice_bowl", "pasta_tomato"], SEL, 1, [], PKGS)
    assert line(res, "onion")["required"] == D("80")
    assert line(res, "onion")["packages_needed"] == 1


def test_decimal_total_is_exact():
    sel = dict(SEL, rice=prod("R", "0.10"), beans=prod("B", "0.20"),
               tomatoes=prod("T", "14.79"), onion=prod("O", "0.01"))
    res = compute_cost(["bean_rice_bowl"], sel, 2, [], PKGS)
    expected = sum((li["unit_price"] * li["packages_needed"] for li in res["line_items"]), D(0))
    assert res["total"] == expected == D("0.10") + D("0.20") + D("14.79") + D("0.01")
    assert isinstance(res["total"], D)
    # 3 packs x 14.79 = 44.37 exactly (floats give 44.370000000000005)
    sel["tomatoes"] = prod("T", "14.79")
    res = compute_cost(["bean_rice_bowl"], sel, 50, [], PKGS)  # tomatoes 3000 g -> 3 packs
    assert line(res, "tomatoes")["line_total"] == D("44.37")


def test_incompatible_package_unit_is_unsupported():
    pk = dict(PKGS, O=Package("onion", D("10"), "count"))  # recipe needs mass
    res = compute_cost(["bean_rice_bowl"], SEL, 2, [], pk)
    assert res["status"] == "unsupported_data" and "incompatible" in res["message"]


def test_missing_price_and_unknown_package_are_unsupported():
    res = compute_cost(["bean_rice_bowl"], dict(SEL, onion=prod("O", None)), 2, [], PKGS)
    assert res["status"] == "unsupported_data" and "price" in res["message"]
    res = compute_cost(["bean_rice_bowl"], dict(SEL, onion=prod("ZZ", "1.00")), 2, [], PKGS)
    assert res["status"] == "unsupported_data" and "package size" in res["message"]
