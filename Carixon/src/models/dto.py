from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AddressDTO(BaseModel):
    address_type: str = Field(examples=["billing", "shipping"])
    street: str
    city: str
    zip_code: str
    country: str = "Česká republika"


class ContactDTO(BaseModel):
    name: str
    role: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None


class CustomerDTO(BaseModel):
    id: Optional[int] = None
    first_name: str
    last_name: str
    phone: str
    city: str = ""
    email: Optional[str] = None
    company: Optional[str] = None
    ico: Optional[str] = None
    dic: Optional[str] = None
    website: Optional[str] = None
    birth_date: Optional[date] = None
    source: Optional[str] = None
    preferred_language: str = "cs"
    notes: str = ""
    archived: bool = False
    addresses: List[AddressDTO] = Field(default_factory=list)
    contacts: List[ContactDTO] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class OrderItemDTO(BaseModel):
    name: str
    description: str = ""
    quantity: float = 1.0
    unit_price: float = 0.0
    vat_rate: float = 21.0

    @property
    def total(self) -> float:
        return round(self.quantity * self.unit_price, 2)


class OrderDTO(BaseModel):
    id: Optional[int] = None
    customer_id: Optional[int] = None
    status: str = "active"
    title: str
    description: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total: float = 0.0
    items: List[OrderItemDTO] = Field(default_factory=list)


class InvoiceItemDTO(BaseModel):
    name: str
    description: str = ""
    unit: str = "ks"
    quantity: float = 1.0
    unit_price: float = 0.0
    discount: float = 0.0
    vat_rate: float = 21.0

    @property
    def subtotal(self) -> float:
        return round(self.quantity * self.unit_price * (1 - self.discount / 100), 2)

    @property
    def vat_total(self) -> float:
        return round(self.subtotal * self.vat_rate / 100, 2)


class InvoiceDTO(BaseModel):
    id: Optional[int] = None
    customer_id: Optional[int] = None
    number: str
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    due_at: datetime
    status: str = "draft"
    currency: str = "CZK"
    note: str = ""
    items: List[InvoiceItemDTO] = Field(default_factory=list)

    @property
    def total(self) -> float:
        return round(sum(item.subtotal + item.vat_total for item in self.items), 2)

    @property
    def vat_total(self) -> float:
        return round(sum(item.vat_total for item in self.items), 2)


class NotificationDTO(BaseModel):
    id: Optional[int] = None
    source: str
    title: str
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    read: bool = False
