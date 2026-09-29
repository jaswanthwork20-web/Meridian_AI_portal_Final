"""
SQLAlchemy Domain Models for Meridian Enterprise Application
Matching exact shopmart.db schema
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
)
from sqlalchemy.orm import relationship
from .connection import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, default="Maya Sharma")
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="customer", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    invoices = relationship("Invoice", back_populates="owner")
    chat_sessions = relationship("ChatSession", back_populates="owner")
    leave_requests = relationship("LeaveRequest", back_populates="employee")

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    show_in_invoice_dropdown = Column(Integer, default=1)
    rating = Column(Float, default=4.5)
    review_count = Column(Integer, default=120)
    category = Column(String, default="Office Tech")
    discount_percent = Column(Integer, default=15)
    image_url = Column(String, nullable=True)
    delivery_estimate = Column(String, default="Tomorrow, 11 AM")

    invoices = relationship("Invoice", back_populates="product")

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    client_name = Column(String, nullable=False, default="Default Client")
    quantity = Column(Integer, nullable=False, default=1)
    tax_code = Column(String, nullable=False, default="GST 18%")
    tax_document_filename = Column(String, nullable=True)
    remarks = Column(Text, nullable=True)
    status = Column(String, default="draft", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="invoices")
    product = relationship("Product", back_populates="invoices")

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, default="New Conversation")
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String, nullable=False)  # "user", "bot", "engineer"
    kind = Column(String, default="text", nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")

class EmployeeMeeting(Base):
    __tablename__ = "employee_meetings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    date_time = Column(String, nullable=False)
    attendees = Column(String, nullable=False)
    link = Column(String, nullable=False)
    status = Column(String, nullable=False, default="Starting soon")
    tags = Column(String, nullable=True)

class EmployeeEmail(Base):
    __tablename__ = "employee_emails"

    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String, nullable=False)
    sender_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    preview = Column(Text, nullable=False)
    timestamp = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    is_urgent = Column(Boolean, default=False)

class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    leave_type = Column(String, nullable=False)
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    days_count = Column(Integer, nullable=False, default=1)
    reason = Column(Text, nullable=False)
    status = Column(String, default="Approved")
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("User", back_populates="leave_requests")

class CompanyProject(Base):
    __tablename__ = "company_projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    client = Column(String, nullable=False)
    status = Column(String, nullable=False)
    progress_pct = Column(Integer, nullable=False, default=0)
    budget_allocated = Column(Float, nullable=False, default=0.0)
    budget_spent = Column(Float, nullable=False, default=0.0)
    deadline = Column(String, nullable=False)
    finance_lead = Column(String, nullable=False)

class JiraTicket(Base):
    __tablename__ = "jira_tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_key = Column(String, unique=True, index=True, nullable=False)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    reporter_email = Column(String, nullable=False)
    summary = Column(String, nullable=False)
    user_query = Column(Text, nullable=False)
    transcript = Column(Text, nullable=False)
    status = Column(String, default="L2 Confirmed")
    priority = Column(String, default="High")
    ticket_url = Column(String, nullable=False)
    is_live = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
