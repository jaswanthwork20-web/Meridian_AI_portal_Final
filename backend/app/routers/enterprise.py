"""
Enterprise Operations Router (Products, Invoices, Meetings, Emails, Leaves, Projects)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import (
    get_db, Product, Invoice, EmployeeMeeting, EmployeeEmail,
    LeaveRequest, CompanyProject, User
)
from app.auth import require_employee, get_current_user
from app.schemas import (
    ProductOut, ProductCreate, InvoiceOut, InvoiceCreate,
    MeetingOut, EmailOut, LeaveDashboardOut, LeaveOut, LeaveCreate,
    CompanyProjectOut, CustomerProductOut
)

router = APIRouter(tags=["Enterprise Operations"])

@router.get("/products", response_model=list[ProductOut])
def get_products(db: Session = Depends(get_db)):
    return db.query(Product).all()

@router.post("/products", response_model=ProductOut)
def create_product(req: ProductCreate, db: Session = Depends(get_db)):
    p = Product(
        name=req.name,
        price=req.price,
        show_in_invoice_dropdown=req.show_in_invoice_dropdown,
        rating=req.rating,
        review_count=req.review_count,
        category=req.category,
        discount_percent=req.discount_percent
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

@router.get("/api/customer/products", response_model=list[CustomerProductOut])
def get_customer_products(db: Session = Depends(get_db)):
    return db.query(Product).all()

@router.get("/invoices", response_model=list[InvoiceOut])
def get_invoices(db: Session = Depends(get_db)):
    return db.query(Invoice).all()

@router.post("/invoices", response_model=InvoiceOut)
def create_invoice(req: InvoiceCreate, current_user: User = Depends(require_employee), db: Session = Depends(get_db)):
    prod = db.query(Product).filter(Product.id == req.product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    inv = Invoice(
        user_id=current_user.id,
        product_id=req.product_id,
        quantity=req.quantity,
        status=req.status,
        tax_code=req.tax_code,
        remarks=req.remarks,
        client_name=req.client_name
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv

@router.patch("/invoices/{invoice_id}", response_model=InvoiceOut)
def update_invoice(invoice_id: int, req: InvoiceCreate, current_user: User = Depends(require_employee), db: Session = Depends(get_db)):
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    inv.client_name = req.client_name
    inv.product_id = req.product_id
    inv.quantity = req.quantity
    inv.tax_code = req.tax_code
    inv.remarks = req.remarks
    inv.status = req.status
    db.commit()
    db.refresh(inv)
    return inv

@router.get("/employee/meetings", response_model=list[MeetingOut])
def get_meetings(db: Session = Depends(get_db)):
    return db.query(EmployeeMeeting).all()

@router.get("/employee/emails", response_model=list[EmailOut])
def get_emails(db: Session = Depends(get_db)):
    return db.query(EmployeeEmail).all()

@router.patch("/employee/emails/{email_id}/toggle-read")
def toggle_email_read(email_id: int, db: Session = Depends(get_db)):
    em = db.query(EmployeeEmail).filter(EmployeeEmail.id == email_id).first()
    if not em:
        raise HTTPException(status_code=404, detail="Email not found")
    em.is_read = not bool(em.is_read)
    db.commit()
    db.refresh(em)
    return {"id": em.id, "is_read": em.is_read}

@router.get("/employee/leaves", response_model=LeaveDashboardOut)
def get_leaves(current_user: User = Depends(require_employee), db: Session = Depends(get_db)):
    requests = db.query(LeaveRequest).filter(LeaveRequest.user_id == current_user.id).all()
    balances = {"Earned Leave": 14, "Sick Leave": 8, "Casual Leave": 5, "Work From Home": 8}
    return LeaveDashboardOut(balances=balances, requests=requests)

@router.post("/employee/leaves", response_model=LeaveOut)
def create_leave(req: LeaveCreate, current_user: User = Depends(require_employee), db: Session = Depends(get_db)):
    leave = LeaveRequest(
        user_id=current_user.id,
        leave_type=req.leave_type,
        start_date=req.start_date,
        end_date=req.end_date,
        days_count=req.days_count,
        reason=req.reason,
        status="Approved"
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave

@router.get("/employee/projects", response_model=list[CompanyProjectOut])
def get_projects(db: Session = Depends(get_db)):
    return db.query(CompanyProject).all()
