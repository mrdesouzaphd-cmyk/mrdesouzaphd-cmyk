"""Frontend web application for the Content-to-Ebook Agent.

Provides a user-friendly upload interface and sales platform
served via Cloud Run.
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Ebook Agent — Upload & Sales")
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.get("/store", response_class=HTMLResponse)
async def store_page(request: Request):
    return templates.TemplateResponse("store.html", {"request": request})


@app.get("/health")
def health():
    return {"status": "healthy", "service": "frontend"}
