"""
Database Package for Meridian Enterprise Application
"""
from .connection import engine, SessionLocal, Base, get_db, DATABASE_URL
from .models import (
    User, Product, Invoice, ChatSession, ChatMessage,
    EmployeeMeeting, EmployeeEmail, LeaveRequest, CompanyProject, JiraTicket
)
from .init_db import init_db

__all__ = [
    "engine", "SessionLocal", "Base", "get_db", "DATABASE_URL",
    "User", "Product", "Invoice", "ChatSession", "ChatMessage",
    "EmployeeMeeting", "EmployeeEmail", "LeaveRequest", "CompanyProject", "JiraTicket",
    "init_db"
]
