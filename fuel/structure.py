"""Fuel boiler categories.

Leaf units (steam boiler / oil boiler) each get their own register page.
"""

BOILERS = (
    {
        "slug": "steam-boiler",
        "name": "Steam Boiler",
        "icon": "bi-cloud-haze2",
        "description": "Steam boiler fuel register",
        "urdu": "بھاپ بوائلر",
    },
    {
        "slug": "oil-boiler",
        "name": "Oil Boiler",
        "icon": "bi-droplet-half",
        "description": "Oil boiler time, Kuttal, Lunda & Fuel register",
        "urdu": "آئل بوائلر",
    },
)

_BY_SLUG = {b["slug"]: b for b in BOILERS}


def get_boiler(slug: str) -> dict | None:
    return _BY_SLUG.get(slug)
