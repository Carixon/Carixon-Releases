from __future__ import annotations

from collections import deque
from typing import Callable, Deque, Iterable, List, Optional

from sqlalchemy import select, text

from ..db import models
from ..db.database import session_scope
from ..models.dto import AddressDTO, ContactDTO, CustomerDTO
from ..utils.logger import get_logger
from ..utils.paths import customer_folder


class HistoryManager:
    def __init__(self, limit: int = 100) -> None:
        self._undo: Deque[tuple[Callable[[], None], Callable[[], None]]] = deque(maxlen=limit)
        self._redo: Deque[tuple[Callable[[], None], Callable[[], None]]] = deque(maxlen=limit)

    def record(self, undo: Callable[[], None], redo: Callable[[], None]) -> None:
        self._undo.append((undo, redo))
        self._redo.clear()

    def undo(self) -> None:
        if not self._undo:
            return
        undo, redo = self._undo.pop()
        undo()
        self._redo.append((undo, redo))

    def redo(self) -> None:
        if not self._redo:
            return
        undo, redo = self._redo.pop()
        redo()
        self._undo.append((undo, redo))


class CustomerService:
    def __init__(self) -> None:
        self._logger = get_logger("CustomerService")
        self._history = HistoryManager()

    def _apply_addresses(self, customer: models.Customer, addresses: Iterable[AddressDTO]) -> None:
        customer.addresses.clear()
        for address in addresses:
            customer.addresses.append(
                models.CustomerAddress(
                    address_type=address.address_type,
                    street=address.street,
                    city=address.city,
                    zip_code=address.zip_code,
                    country=address.country,
                )
            )

    def _apply_contacts(self, customer: models.Customer, contacts: Iterable[ContactDTO]) -> None:
        customer.contacts.clear()
        for contact in contacts:
            customer.contacts.append(
                models.CustomerContact(
                    name=contact.name,
                    role=contact.role,
                    email=contact.email,
                    phone=contact.phone,
                )
            )

    def _apply_tags(self, customer: models.Customer, tags: Iterable[str]) -> None:
        customer.tags.clear()
        for tag in tags:
            customer.tags.append(models.CustomerTag(name=tag))

    def _apply_dto(self, customer: models.Customer, dto: CustomerDTO) -> None:
        customer.first_name = dto.first_name
        customer.last_name = dto.last_name
        customer.phone = dto.phone
        customer.city = dto.city
        customer.email = dto.email
        customer.company = dto.company
        customer.ico = dto.ico
        customer.dic = dto.dic
        customer.website = dto.website
        customer.birth_date = dto.birth_date
        customer.source = dto.source
        customer.preferred_language = dto.preferred_language
        customer.notes = dto.notes
        customer.archived = dto.archived
        self._apply_addresses(customer, dto.addresses)
        self._apply_contacts(customer, dto.contacts)
        self._apply_tags(customer, dto.tags)

    def create(self, dto: CustomerDTO) -> CustomerDTO:
        with session_scope() as session:
            customer = models.Customer()
            self._apply_dto(customer, dto)
            session.add(customer)
            session.flush()
            customer_folder(customer.id, customer.full_name)
            session.flush()
            session.refresh(customer)
            self._logger.info("Created customer %s", customer.full_name)
            dto.id = customer.id
            snapshot = self._to_dto(customer)

        def undo() -> None:
            with session_scope() as undo_session:
                instance = undo_session.get(models.Customer, snapshot.id)
                if instance:
                    undo_session.delete(instance)

        def redo() -> None:
            with session_scope() as redo_session:
                instance = models.Customer()
                instance.id = snapshot.id
                self._apply_dto(instance, snapshot)
                redo_session.add(instance)
                customer_folder(snapshot.id or 0, snapshot.full_name)

        self._history.record(undo, redo)
        return dto

    def update(self, customer_id: int, dto: CustomerDTO) -> CustomerDTO:
        with session_scope() as session:
            customer = session.get(models.Customer, customer_id)
            if not customer:
                raise ValueError("Customer not found")
            before = self._to_dto(customer)
            self._apply_dto(customer, dto)
            session.add(customer)
            session.flush()
            self._logger.info("Updated customer %s", customer.full_name)
            dto.id = customer.id

        after = dto

        def undo() -> None:
            with session_scope() as undo_session:
                instance = undo_session.get(models.Customer, customer_id)
                if instance:
                    self._apply_dto(instance, before)
                    undo_session.add(instance)

        def redo() -> None:
            with session_scope() as redo_session:
                instance = redo_session.get(models.Customer, customer_id)
                if instance:
                    self._apply_dto(instance, after)
                    redo_session.add(instance)

        self._history.record(undo, redo)
        return dto

    def soft_delete(self, customer_id: int) -> None:
        with session_scope() as session:
            customer = session.get(models.Customer, customer_id)
            if customer:
                previous = customer.archived
                customer.archived = True
                session.add(customer)

        def undo() -> None:
            with session_scope() as undo_session:
                instance = undo_session.get(models.Customer, customer_id)
                if instance:
                    instance.archived = previous
                    undo_session.add(instance)

        def redo() -> None:
            with session_scope() as redo_session:
                instance = redo_session.get(models.Customer, customer_id)
                if instance:
                    instance.archived = True
                    redo_session.add(instance)

        self._history.record(undo, redo)

    def restore(self, customer_id: int) -> None:
        with session_scope() as session:
            customer = session.get(models.Customer, customer_id)
            if customer:
                previous = customer.archived
                customer.archived = False
                session.add(customer)

        def undo() -> None:
            with session_scope() as undo_session:
                instance = undo_session.get(models.Customer, customer_id)
                if instance:
                    instance.archived = previous
                    undo_session.add(instance)

        def redo() -> None:
            with session_scope() as redo_session:
                instance = redo_session.get(models.Customer, customer_id)
                if instance:
                    instance.archived = False
                    redo_session.add(instance)

        self._history.record(undo, redo)

    def delete(self, customer_id: int) -> None:
        with session_scope() as session:
            customer = session.get(models.Customer, customer_id)
            if customer:
                snapshot = self._to_dto(customer)
                session.delete(customer)

        def undo() -> None:
            with session_scope() as undo_session:
                instance = models.Customer()
                instance.id = snapshot.id
                self._apply_dto(instance, snapshot)
                undo_session.add(instance)
                customer_folder(snapshot.id or 0, snapshot.full_name)

        def redo() -> None:
            with session_scope() as redo_session:
                instance = redo_session.get(models.Customer, snapshot.id)
                if instance:
                    redo_session.delete(instance)

        self._history.record(undo, redo)

    def undo(self) -> None:
        self._history.undo()

    def redo(self) -> None:
        self._history.redo()

    def list(self, include_archived: bool = False) -> List[CustomerDTO]:
        with session_scope() as session:
            query = select(models.Customer)
            if not include_archived:
                query = query.where(models.Customer.archived.is_(False))
            customers = session.scalars(query).all()
            return [self._to_dto(customer) for customer in customers]

    def search(self, phrase: str) -> List[CustomerDTO]:
        with session_scope() as session:
            result = session.execute(
                text(
                    "SELECT c.id FROM customers c JOIN customers_fts f ON c.id = f.rowid WHERE customers_fts MATCH :phrase"
                ),
                {"phrase": phrase},
            )
            ids = [row[0] for row in result.fetchall()]
            customers = [session.get(models.Customer, customer_id) for customer_id in ids]
            return [self._to_dto(customer) for customer in customers if customer]

    def _to_dto(self, customer: models.Customer) -> CustomerDTO:
        dto = CustomerDTO(
            id=customer.id,
            first_name=customer.first_name,
            last_name=customer.last_name,
            phone=customer.phone,
            city=customer.city,
            email=customer.email,
            company=customer.company,
            ico=customer.ico,
            dic=customer.dic,
            website=customer.website,
            birth_date=customer.birth_date,
            source=customer.source,
            preferred_language=customer.preferred_language,
            notes=customer.notes,
            archived=customer.archived,
            addresses=[
                AddressDTO(
                    address_type=address.address_type,
                    street=address.street,
                    city=address.city,
                    zip_code=address.zip_code,
                    country=address.country,
                )
                for address in customer.addresses
            ],
            contacts=[
                ContactDTO(name=contact.name, role=contact.role, email=contact.email, phone=contact.phone)
                for contact in customer.contacts
            ],
            tags=[tag.name for tag in customer.tags],
        )
        return dto


customer_service = CustomerService()
