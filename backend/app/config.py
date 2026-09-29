"""
Application Configuration & Environment Settings
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Project root and backend package root
BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = BASE_DIR / "backend"

# Load .env file
load_dotenv(BASE_DIR / ".env")

# Server Config
PORT = int(os.getenv("PORT", "8001"))
HOST = os.getenv("HOST", "0.0.0.0")

# Security & JWT
JWT_SECRET = os.getenv("JWT_SECRET")
if os.getenv("ENVIRONMENT", "development").lower() == "production":
	if not JWT_SECRET or len(JWT_SECRET) < 32:
		raise RuntimeError("Production requires a JWT_SECRET of at least 32 characters")
JWT_SECRET = JWT_SECRET or os.urandom(32).hex()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# Database
DATABASE_DIR = BACKEND_DIR / "database"
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DATABASE_DIR / "shopmart.db")))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")

# Uploads Directory
UPLOAD_DIR = BACKEND_DIR / "uploaded_tax_documents"
UPLOAD_DIR.mkdir(exist_ok=True)

# Templates Directory
TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"
STATIC_DIR = BASE_DIR / "frontend" / "static"

# Knowledge Base & RAG Paths
KB_DIR = BACKEND_DIR / "knowledge_base"
KB_DATA_DIR = KB_DIR / "data"

# CORS is disabled for credentials; the browser uses same-origin API requests.
CORS_ORIGINS = [
	origin.strip()
	for origin in os.getenv("CORS_ORIGINS", "http://localhost,http://127.0.0.1").split(",")
	if origin.strip()
]

# MeshCentral
MESHCENTRAL_URL = os.getenv("MESHCENTRAL_URL", "wss://localhost:443")
MESHCENTRAL_USER = os.getenv("MESHCENTRAL_USER", "")
MESHCENTRAL_PASS = os.getenv("MESHCENTRAL_PASS", "")
MESHCTRL_PATH = os.getenv("MESHCTRL_PATH", "")

# Atlassian Jira
JIRA_INSTANCE_URL = os.getenv("JIRA_INSTANCE_URL", "")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "KAN")

# Atlassian Confluence
CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_BASE_URL", "")
CONFLUENCE_EMAIL = os.getenv("CONFLUENCE_EMAIL", "")
CONFLUENCE_API_KEY = os.getenv("CONFLUENCE_API_KEY", "")
CONFLUENCE_SPACE_KEY = os.getenv("CONFLUENCE_SPACE_KEY", "SELFHELP")

# AWS Bedrock
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

# Confidence Thresholds
CONFIDENCE_THRESHOLD = 0.45
