import sys
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

sys.path.insert(0, str(BACKEND_DIR))

from main import app


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(ROOT_DIR / "home.html")


app.mount(
    "/",
    StaticFiles(directory=ROOT_DIR, html=True),
    name="frontend"
)
