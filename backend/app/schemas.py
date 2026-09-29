"""
Pydantic API Schemas for Meridian Enterprise Helpdesk
"""
from pydantic import BaseModel, EmailStr
from datetime import datetime

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str = "customer"

class UserProfileOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    created_at: datetime | None = None

    class Config:
        from_attributes = True

class MeetingOut(BaseModel):
    id: int
    title: str
    date_time: str
    attendees: str
    link: str
    status: str = "Starting soon"
    tags: str | None = None

    class Config:
        from_attributes = True

class EmailOut(BaseModel):
    id: int
    sender: str
    sender_email: str
    subject: str
    preview: str
    timestamp: str
    is_read: bool | int = False
    is_urgent: bool | int = False

    class Config:
        from_attributes = True

class LeaveOut(BaseModel):
    id: int
    leave_type: str
    start_date: str
    end_date: str
    days_count: int = 1
    reason: str
    status: str = "Approved"
    created_at: datetime | str | None = None

    class Config:
        from_attributes = True

class LeaveCreate(BaseModel):
    leave_type: str
    start_date: str
    end_date: str
    reason: str
    days_count: int = 1

class LeaveDashboardOut(BaseModel):
    balances: dict[str, int]
    requests: list[LeaveOut]

class CompanyProjectOut(BaseModel):
    id: int
    title: str
    client: str
    status: str
    progress_pct: int = 0
    budget_allocated: float = 0.0
    budget_spent: float = 0.0
    deadline: str
    finance_lead: str

    class Config:
        from_attributes = True

class SessionOut(BaseModel):
    id: int
    title: str

    class Config:
        from_attributes = True

class MessageIn(BaseModel):
    message: str

class MessageOut(BaseModel):
    id: int | None = None
    session_id: int | None = None
    role: str
    kind: str
    content: str
    created_at: datetime | None = None

    class Config:
        from_attributes = True

class FeedbackIn(BaseModel):
    action: str  # "resolved" or "not_resolved"
    message_id: int | None = None

class ChatReplyOut(BaseModel):
    escalate: bool
    top_score: float
    matches: list
    tool_used: str | None = None
    tool_status: str | None = None

class ProductOut(BaseModel):
    id: int
    name: str
    price: float
    show_in_invoice_dropdown: int = 1
    rating: float = 4.5
    review_count: int = 120
    category: str = "Office Tech"
    discount_percent: int = 15
    image_url: str | None = None
    delivery_estimate: str = "Tomorrow, 11 AM"

    class Config:
        from_attributes = True

class ProductCreate(BaseModel):
    name: str
    price: float
    show_in_invoice_dropdown: int = 1
    rating: float = 4.5
    review_count: int = 120
    category: str = "Office Tech"
    discount_percent: int = 15

class InvoiceCreate(BaseModel):
    client_name: str
    product_id: int
    quantity: int = 1
    tax_code: str = "GST 18%"
    remarks: str | None = None
    status: str = "draft"

class InvoiceOut(BaseModel):
    id: int
    user_id: int
    product_id: int
    client_name: str
    quantity: int = 1
    tax_code: str = "GST 18%"
    tax_document_filename: str | None = None
    remarks: str | None = None
    status: str = "draft"
    created_at: datetime | str | None = None

    class Config:
        from_attributes = True

class CustomerProductOut(BaseModel):
    id: int
    name: str
    price: float
    rating: float = 4.5
    review_count: int = 120
    category: str = "Office Tech"
    discount_percent: int = 15
    image_url: str | None = None
    delivery_estimate: str = "Tomorrow, 11 AM"

    class Config:
        from_attributes = True
