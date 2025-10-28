from __future__ import annotations

from datetime import date, datetime
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(120))
    last_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(50))
    city: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    company: Mapped[str | None] = mapped_column(String(180), nullable=True)
    ico: Mapped[str | None] = mapped_column(String(30), nullable=True)
    dic: Mapped[str | None] = mapped_column(String(30), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(5), default="cs")
    notes: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    addresses: Mapped[List[CustomerAddress]] = relationship("CustomerAddress", back_populates="customer", cascade="all, delete-orphan")
    contacts: Mapped[List[CustomerContact]] = relationship("CustomerContact", back_populates="customer", cascade="all, delete-orphan")
    tags: Mapped[List[CustomerTag]] = relationship("CustomerTag", back_populates="customer", cascade="all, delete-orphan")
    orders: Mapped[List[Order]] = relationship("Order", back_populates="customer", cascade="all, delete-orphan")
    invoices: Mapped[List[Invoice]] = relationship("Invoice", back_populates="customer", cascade="all, delete-orphan")
    attachments: Mapped[List[Attachment]] = relationship("Attachment", back_populates="customer", cascade="all, delete-orphan")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class CustomerAddress(Base):
    __tablename__ = "customer_addresses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    address_type: Mapped[str] = mapped_column(String(20))
    street: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(120))
    zip_code: Mapped[str] = mapped_column(String(30))
    country: Mapped[str] = mapped_column(String(120), default="Česká republika")

    customer: Mapped[Customer] = relationship("Customer", back_populates="addresses")


class CustomerContact(Base):
    __tablename__ = "customer_contacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    customer: Mapped[Customer] = relationship("Customer", back_populates="contacts")


class CustomerTag(Base):
    __tablename__ = "customer_tags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(64))

    customer: Mapped[Customer] = relationship("Customer", back_populates="tags")


class OrderStatusEnum(str, PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DONE = "done"
    PAID = "paid"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default=OrderStatusEnum.ACTIVE.value)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total: Mapped[float] = mapped_column(Float, default=0.0)

    customer: Mapped[Optional[Customer]] = relationship("Customer", back_populates="orders")
    items: Mapped[List[OrderItem]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    invoices: Mapped[List[Invoice]] = relationship("Invoice", secondary="order_invoices", back_populates="orders")
    attachments: Mapped[List[Attachment]] = relationship("Attachment", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    vat_rate: Mapped[float] = mapped_column(Float, default=21.0)

    order: Mapped[Order] = relationship("Order", back_populates="items")


order_invoices = Table(
    "order_invoices",
    Base.metadata,
    Column("order_id", ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True),
    Column("invoice_id", ForeignKey("invoices.id", ondelete="CASCADE"), primary_key=True),
)


class InvoiceStatusEnum(str, PyEnum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    number: Mapped[str] = mapped_column(String(64), unique=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    due_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default=InvoiceStatusEnum.DRAFT.value)
    currency: Mapped[str] = mapped_column(String(10), default="CZK")
    total: Mapped[float] = mapped_column(Float, default=0.0)
    vat_total: Mapped[float] = mapped_column(Float, default=0.0)
    note: Mapped[str] = mapped_column(Text, default="")
    pdf_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    customer: Mapped[Optional[Customer]] = relationship("Customer", back_populates="invoices")
    items: Mapped[List[InvoiceItem]] = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    orders: Mapped[List[Order]] = relationship("Order", secondary=order_invoices, back_populates="invoices")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    unit: Mapped[str] = mapped_column(String(32), default="ks")
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    discount: Mapped[float] = mapped_column(Float, default=0.0)
    vat_rate: Mapped[float] = mapped_column(Float, default=21.0)

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="items")


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"))
    file_path: Mapped[str] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped[Optional[Customer]] = relationship("Customer", back_populates="attachments")
    order: Mapped[Optional[Order]] = relationship("Order", back_populates="attachments")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(32))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user: Mapped[str] = mapped_column(String(64), default="system")
    details: Mapped[str] = mapped_column(Text, default="")


class BackupJob(Base):
    __tablename__ = "backup_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    path: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, default=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
