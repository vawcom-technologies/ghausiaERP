"""Start the ERP for Railway or any host that sets PORT."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(args):
    subprocess.check_call([sys.executable, *args], cwd=ROOT)


def main():
    os.chdir(ROOT)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)

    run(["manage.py", "migrate", "--noinput"])
    run(["manage.py", "collectstatic", "--noinput"])
    if os.getenv("SEED_DEMO_DATA", "true").lower() in ("true", "1", "yes"):
        run(["manage.py", "seed_demo_data"])

    from waitress import serve

    from config.wsgi import application

    port = int(os.environ.get("PORT", "8000"))
    serve(application, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
