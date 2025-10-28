from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import select

from ..db import models
from ..db.database import session_scope
from ..models.dto import OrderDTO, OrderItemDTO
from ..utils.logger import get_logger


class OrderService:
    def __init__(self) -> None:
        self._logger = get_logger("OrderService")

    def create(self, dto: OrderDTO) -> OrderDTO:
        with session_scope() as session:
            order = models.Order(
                customer_id=dto.customer_id,
                status=dto.status,
                title=dto.title,
                description=dto.description,
                created_at=dto.created_at,
                due_date=dto.due_date,
                completed_at=dto.completed_at,
                total=dto.total,
            )
            session.add(order)
            session.flush()
            self._apply_items(order, dto.items)
            session.add(order)
            session.flush()
            session.refresh(order)
            self._logger.info("Created order #%s", order.id)
            dto.id = order.id
            return dto

    def update(self, order_id: int, dto: OrderDTO) -> OrderDTO:
        with session_scope() as session:
            order = session.get(models.Order, order_id)
            if not order:
                raise ValueError("Order not found")
            order.customer_id = dto.customer_id
            order.status = dto.status
            order.title = dto.title
            order.description = dto.description
            order.due_date = dto.due_date
            order.completed_at = dto.completed_at
            order.total = dto.total
            self._apply_items(order, dto.items)
            session.add(order)
            session.flush()
            session.refresh(order)
            return self._to_dto(order)

    def change_status(self, order_id: int, status: str) -> OrderDTO:
        with session_scope() as session:
            order = session.get(models.Order, order_id)
            if not order:
                raise ValueError("Order not found")
            order.status = status
            if status == models.OrderStatusEnum.DONE.value:
                order.completed_at = datetime.utcnow()
            session.add(order)
            session.flush()
            session.refresh(order)
            return self._to_dto(order)

    def list(self, status: Optional[str] = None) -> List[OrderDTO]:
        with session_scope() as session:
            query = select(models.Order)
            if status:
                query = query.where(models.Order.status == status)
            orders = session.scalars(query.order_by(models.Order.created_at.desc())).all()
            return [self._to_dto(order) for order in orders]

    def _apply_items(self, order: models.Order, items: List[OrderItemDTO]) -> None:
        order.items.clear()
        for item in items:
            order.items.append(
                models.OrderItem(
                    name=item.name,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    vat_rate=item.vat_rate,
                )
            )
        order.total = sum(item.quantity * item.unit_price for item in order.items)

    def _to_dto(self, order: models.Order) -> OrderDTO:
        return OrderDTO(
            id=order.id,
            customer_id=order.customer_id,
            status=order.status,
            title=order.title,
            description=order.description,
            created_at=order.created_at,
            due_date=order.due_date,
            completed_at=order.completed_at,
            total=order.total,
            items=[
                OrderItemDTO(
                    name=item.name,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    vat_rate=item.vat_rate,
                )
                for item in order.items
            ],
        )


order_service = OrderService()
