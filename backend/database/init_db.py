"""
Database Initialization & Migrations
"""
from .connection import engine, Base
from .models import (
    User, Product, Invoice, ChatSession, ChatMessage,
    EmployeeMeeting, EmployeeEmail, LeaveRequest, CompanyProject, JiraTicket
)

def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        import sqlite3
        raw_conn = conn.connection
        cursor = raw_conn.cursor()

        # Check and migrate users columns
        cursor.execute("PRAGMA table_info(users)")
        user_cols = [c[1] for c in cursor.fetchall()]
        if "role" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'customer'")
        if "name" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN name TEXT DEFAULT 'Maya Sharma'")

        # Check and migrate products columns
        cursor.execute("PRAGMA table_info(products)")
        prod_cols = [c[1] for c in cursor.fetchall()]
        migrations = [
            ("rating", "REAL DEFAULT 4.5"),
            ("review_count", "INTEGER DEFAULT 120"),
            ("category", "TEXT DEFAULT 'Office Tech'"),
            ("discount_percent", "INTEGER DEFAULT 15"),
            ("image_url", "TEXT"),
            ("delivery_estimate", "TEXT DEFAULT 'Tomorrow, 11 AM'"),
        ]
        for col_name, col_def in migrations:
            if col_name not in prod_cols:
                cursor.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_def}")
        raw_conn.commit()

    print(f"[Database] Initialized with tables: {', '.join(Base.metadata.tables.keys())}")

if __name__ == "__main__":
    init_db()
