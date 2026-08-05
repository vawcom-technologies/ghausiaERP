"""Attendance department / section tree.

Leaf units (department with no sections, or a section under a department)
each get their own attendance register page. Columns and employees will be
wired later.
"""

DEPARTMENTS = (
    {
        "slug": "admin",
        "name": "Admin",
        "icon": "bi-briefcase",
        "description": "Accounts office and ADMs",
        "sections": (
            {
                "slug": "accounts-office",
                "name": "Accounts Office",
                "icon": "bi-calculator",
                "description": "Accounts office attendance",
            },
            {
                "slug": "adms",
                "name": "ADMs",
                "icon": "bi-person-badge",
                "description": "ADMs attendance",
            },
        ),
    },
    {
        "slug": "kora",
        "name": "Kora",
        "icon": "bi-layers",
        "description": "Kora department attendance",
        "sections": (),
    },
    {
        "slug": "singeing",
        "name": "Singeing",
        "icon": "bi-fire",
        "description": "Singeing department attendance",
        "sections": (),
    },
    {
        "slug": "dyeing",
        "name": "Dyeing",
        "icon": "bi-droplet-half",
        "description": "Jet, color room, jugar, and drying",
        "sections": (
            {
                "slug": "jet",
                "name": "Jet",
                "icon": "bi-water",
                "description": "Jet attendance",
            },
            {
                "slug": "color-room",
                "name": "Color Room",
                "icon": "bi-palette",
                "description": "Color room attendance",
            },
            {
                "slug": "jugar-machine",
                "name": "Jugar Machine",
                "icon": "bi-gear-wide-connected",
                "description": "Jugar machine attendance",
            },
            {
                "slug": "drying-machine",
                "name": "Drying Machine",
                "icon": "bi-wind",
                "description": "Drying machine attendance",
            },
        ),
    },
)

_BY_SLUG = {d["slug"]: d for d in DEPARTMENTS}


def get_department(slug: str) -> dict | None:
    return _BY_SLUG.get(slug)


def get_section(dept_slug: str, section_slug: str) -> tuple[dict, dict] | tuple[None, None]:
    dept = get_department(dept_slug)
    if not dept:
        return None, None
    for section in dept["sections"]:
        if section["slug"] == section_slug:
            return dept, section
    return None, None
