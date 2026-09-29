"""
Frontend HTML Page Router
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse
from app.config import TEMPLATES_DIR

router = APIRouter(tags=["Frontend Pages"])

def get_template_path(filename: str) -> str:
    tpl = TEMPLATES_DIR / filename
    if not tpl.is_file():
        raise FileNotFoundError(f"Frontend template not found: {filename}")
    return str(tpl)

@router.get("/")
@router.get("/portal")
@router.get("/employee_portal.html")
def employee_portal():
    return FileResponse(get_template_path("employee_portal.html"), media_type="text/html")

@router.get("/login")
@router.get("/login.html")
def login_page():
    return FileResponse(get_template_path("login.html"), media_type="text/html")

@router.get("/customer_store.html")
def customer_store_page():
    return FileResponse(get_template_path("customer_store.html"), media_type="text/html")

