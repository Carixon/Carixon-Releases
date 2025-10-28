from __future__ import annotations

from datetime import datetime
from typing import Iterable, List

import requests

from ..db import models
from ..db.database import session_scope
from ..models.dto import CustomerDTO, NotificationDTO
from ..utils.logger import get_logger

CARIXON_ALERTS_URL = "https://www.carixon.site/api/alerts.json"
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwQEuevjug-oDnS1zcZjcFC4SmSwspzQtgoDMzXl4a96J6cAsFgbJTwDkGQ9ejoXzss/exec"


class SyncService:
    def __init__(self) -> None:
        self._logger = get_logger("SyncService")

    def push_customers_to_sheets(self, service_account_path: str, sheet_id: str) -> int:
        from google.oauth2.service_account import Credentials
        import gspread

        creds = Credentials.from_service_account_file(service_account_path, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1

        with session_scope() as session:
            rows = session.query(models.Customer).all()
            data = [[customer.id, customer.full_name, customer.phone, customer.email or "", customer.city] for customer in rows]
        sheet.clear()
        sheet.append_row(["ID", "Name", "Phone", "Email", "City"])
        if data:
            sheet.append_rows(data)
        self._logger.info("Pushed %s customers to Google Sheets", len(data))
        return len(data)

    def pull_customers_from_sheets(self, service_account_path: str, sheet_id: str) -> List[CustomerDTO]:
        from google.oauth2.service_account import Credentials
        import gspread

        creds = Credentials.from_service_account_file(service_account_path, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1
        rows = sheet.get_all_records()
        customers: List[CustomerDTO] = []
        for row in rows:
            customers.append(
                CustomerDTO(
                    id=row.get("ID"),
                    first_name=row.get("Name", "").split(" ")[0],
                    last_name=" ".join(row.get("Name", "").split(" ")[1:]) or "",
                    phone=row.get("Phone", ""),
                    email=row.get("Email") or None,
                    city=row.get("City", ""),
                )
            )
        self._logger.info("Pulled %s customers from Google Sheets", len(customers))
        return customers

    def fetch_google_script_notifications(self) -> List[NotificationDTO]:
        response = requests.get(GOOGLE_SCRIPT_URL, timeout=10)
        response.raise_for_status()
        payload = response.json()
        notifications = [
            NotificationDTO(source="google_script", title=item["title"], message=item["message"], created_at=datetime.utcnow())
            for item in payload.get("notifications", [])
        ]
        self._store_notifications(notifications)
        return notifications

    def fetch_carixon_alerts(self) -> List[NotificationDTO]:
        response = requests.get(CARIXON_ALERTS_URL, timeout=10)
        response.raise_for_status()
        payload = response.json()
        notifications = [
            NotificationDTO(source="carixon_site", title=item["title"], message=item["message"], created_at=datetime.utcnow())
            for item in payload.get("alerts", [])
        ]
        self._store_notifications(notifications)
        return notifications

    def _store_notifications(self, notifications: Iterable[NotificationDTO]) -> None:
        with session_scope() as session:
            for notification in notifications:
                session.add(
                    models.Notification(
                        source=notification.source,
                        title=notification.title,
                        message=notification.message,
                        created_at=notification.created_at,
                    )
                )

    def unread_notifications(self) -> List[NotificationDTO]:
        with session_scope() as session:
            rows = session.query(models.Notification).filter(models.Notification.read.is_(False)).all()
            return [
                NotificationDTO(
                    id=row.id,
                    source=row.source,
                    title=row.title,
                    message=row.message,
                    created_at=row.created_at,
                    read=row.read,
                )
                for row in rows
            ]

    def mark_notification_read(self, notification_id: int) -> None:
        with session_scope() as session:
            row = session.get(models.Notification, notification_id)
            if row:
                row.read = True
                session.add(row)


sync_service = SyncService()
