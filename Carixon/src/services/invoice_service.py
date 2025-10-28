from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Sequence

from fpdf import FPDF
from sqlalchemy import select

from ..db import models
from ..db.database import session_scope
from ..models.dto import InvoiceDTO, InvoiceItemDTO, OrderDTO
from ..utils.logger import get_logger
from ..utils.paths import ASSETS_DIR, customer_folder


class InvoiceService:
    def __init__(self) -> None:
        self._logger = get_logger("InvoiceService")

    def _generate_number(self, session) -> str:
        today = datetime.today()
        prefix = f"{today.year}/{today.month:02d}"
        existing = session.execute(
            select(models.Invoice.number).where(models.Invoice.number.like(f"{prefix}/%"))
        ).scalars().all()
        return f"{prefix}/{len(existing) + 1:04d}"

    def create(self, dto: InvoiceDTO, order_ids: Sequence[int] | None = None) -> InvoiceDTO:
        with session_scope() as session:
            number = dto.number or self._generate_number(session)
            invoice = models.Invoice(
                customer_id=dto.customer_id,
                number=number,
                issued_at=dto.issued_at,
                due_at=dto.due_at,
                status=dto.status,
                currency=dto.currency,
                note=dto.note,
                total=dto.total,
                vat_total=dto.vat_total,
            )
            session.add(invoice)
            session.flush()
            self._apply_items(invoice, dto.items)
            if order_ids:
                orders = session.query(models.Order).filter(models.Order.id.in_(order_ids)).all()
                invoice.orders.extend(orders)
            session.add(invoice)
            session.flush()
            session.refresh(invoice)
            pdf_path = self._render_pdf(invoice)
            invoice.pdf_path = str(pdf_path)
            session.add(invoice)
            session.flush()
            dto.id = invoice.id
            dto.number = number
            return dto

    def _apply_items(self, invoice: models.Invoice, items: Iterable[InvoiceItemDTO]) -> None:
        invoice.items.clear()
        for item in items:
            invoice.items.append(
                models.InvoiceItem(
                    name=item.name,
                    description=item.description,
                    unit=item.unit,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    discount=item.discount,
                    vat_rate=item.vat_rate,
                )
            )
        total = 0.0
        vat_total = 0.0
        for item in invoice.items:
            subtotal = item.quantity * item.unit_price * (1 - item.discount / 100)
            vat_amount = subtotal * item.vat_rate / 100
            total += subtotal + vat_amount
            vat_total += vat_amount
        invoice.total = round(total, 2)
        invoice.vat_total = round(vat_total, 2)

    def _render_pdf(self, invoice: models.Invoice) -> Path:
        customer_name = invoice.customer.full_name if invoice.customer else "customer"
        folder = customer_folder(invoice.customer_id or 0, customer_name)
        pdf_path = folder / f"invoice_{invoice.number.replace('/', '_')}.pdf"

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        font_path = ASSETS_DIR / "fonts" / "DejaVuSans.ttf"
        if font_path.exists():
            pdf.add_font("DejaVu", "", str(font_path))
            pdf.set_font("DejaVu", size=14)
        else:
            pdf.set_font("Helvetica", size=14)
        pdf.cell(0, 10, txt=f"Faktura {invoice.number}", ln=True)
        pdf.set_font_size(10)
        pdf.cell(0, 8, txt=f"Datum vystavení: {invoice.issued_at:%d.%m.%Y}", ln=True)
        pdf.cell(0, 8, txt=f"Datum splatnosti: {invoice.due_at:%d.%m.%Y}", ln=True)
        pdf.ln(4)
        pdf.cell(0, 8, txt=f"Odběratel: {customer_name}", ln=True)
        pdf.ln(4)

        pdf.set_font_size(9)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(60, 8, "Položka", border=1, fill=True)
        pdf.cell(20, 8, "MJ", border=1, fill=True)
        pdf.cell(20, 8, "Množství", border=1, fill=True)
        pdf.cell(30, 8, "Cena", border=1, fill=True)
        pdf.cell(20, 8, "Sleva", border=1, fill=True)
        pdf.cell(20, 8, "DPH", border=1, fill=True)
        pdf.cell(20, 8, "Celkem", border=1, ln=True, fill=True)

        for item in invoice.items:
            subtotal = item.quantity * item.unit_price * (1 - item.discount / 100)
            vat_amount = subtotal * item.vat_rate / 100
            line_total = subtotal + vat_amount
            pdf.cell(60, 8, item.name, border=1)
            pdf.cell(20, 8, item.unit, border=1)
            pdf.cell(20, 8, f"{item.quantity:.2f}", border=1)
            pdf.cell(30, 8, f"{item.unit_price:.2f}", border=1)
            pdf.cell(20, 8, f"{item.discount:.0f}%", border=1)
            pdf.cell(20, 8, f"{item.vat_rate:.0f}%", border=1)
            pdf.cell(20, 8, f"{line_total:.2f}", border=1, ln=True)

        pdf.ln(4)
        pdf.cell(0, 8, txt=f"DPH celkem: {invoice.vat_total:.2f} {invoice.currency}", ln=True)
        pdf.cell(0, 8, txt=f"K úhradě: {invoice.total:.2f} {invoice.currency}", ln=True)
        pdf.output(str(pdf_path))
        self._logger.info("Generated invoice PDF %s", pdf_path)
        return pdf_path

    def list(self, status: str | None = None) -> List[InvoiceDTO]:
        with session_scope() as session:
            query = select(models.Invoice)
            if status:
                query = query.where(models.Invoice.status == status)
            invoices = session.scalars(query.order_by(models.Invoice.issued_at.desc())).all()
            return [self._to_dto(invoice) for invoice in invoices]

    def _to_dto(self, invoice: models.Invoice) -> InvoiceDTO:
        return InvoiceDTO(
            id=invoice.id,
            customer_id=invoice.customer_id,
            number=invoice.number,
            issued_at=invoice.issued_at,
            due_at=invoice.due_at,
            status=invoice.status,
            currency=invoice.currency,
            note=invoice.note,
            items=[
                InvoiceItemDTO(
                    name=item.name,
                    description=item.description,
                    unit=item.unit,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    discount=item.discount,
                    vat_rate=item.vat_rate,
                )
                for item in invoice.items
            ],
        )


invoice_service = InvoiceService()
