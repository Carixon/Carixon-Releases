from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ...i18n.localization import i18n
from ...services.invoice_service import invoice_service
from ...services.order_service import order_service
from ...services.sync_service import sync_service
from ...utils.logger import get_logger


class DashboardView(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=24)
        self._logger = get_logger("DashboardView")
        self._stats_labels: dict[str, ttk.Label] = {}
        self._canvas: FigureCanvasTkAgg | None = None
        self._create_layout()
        self.refresh()

    def _create_layout(self) -> None:
        stats_frame = ttk.Frame(self)
        stats_frame.pack(fill="x")
        for index, key in enumerate(["active_orders", "unpaid_invoices", "today_events"]):
            card = ttk.Frame(stats_frame, style="Card.TFrame", padding=16)
            card.grid(row=0, column=index, sticky="nsew", padx=12, pady=8)
            stats_frame.columnconfigure(index, weight=1)
            title = ttk.Label(card, text=i18n.translate(f"dashboard.{key}"), font=("Segoe UI", 12, "bold"))
            title.pack(anchor="w")
            value = ttk.Label(card, text="0", font=("Segoe UI", 24))
            value.pack(anchor="w", pady=(8, 0))
            self._stats_labels[key] = value

        chart_frame = ttk.Frame(self, style="Card.TFrame", padding=16)
        chart_frame.pack(fill="both", expand=True, pady=16)
        chart_title = ttk.Label(chart_frame, text=i18n.translate("dashboard.revenue"), font=("Segoe UI", 12, "bold"))
        chart_title.pack(anchor="w")
        self._figure = Figure(figsize=(6, 3), dpi=100)
        self._axes = self._figure.add_subplot(111)
        self._canvas = FigureCanvasTkAgg(self._figure, master=chart_frame)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

        notifications_frame = ttk.Frame(self, style="Card.TFrame", padding=16)
        notifications_frame.pack(fill="both", expand=True)
        title = ttk.Label(
            notifications_frame,
            text=i18n.translate("dashboard.notifications"),
            font=("Segoe UI", 12, "bold"),
        )
        title.pack(anchor="w")
        self._notifications_list = tk.Listbox(notifications_frame, height=6)
        self._notifications_list.pack(fill="both", expand=True, pady=(8, 0))

    def refresh(self) -> None:
        active_orders = len(order_service.list(status="active"))
        unpaid = len(invoice_service.list(status="issued"))
        today = datetime.today().date()
        todays_orders = [order for order in order_service.list() if order.due_date and order.due_date.date() == today]

        self._stats_labels["active_orders"].config(text=str(active_orders))
        self._stats_labels["unpaid_invoices"].config(text=str(unpaid))
        self._stats_labels["today_events"].config(text=str(len(todays_orders)))

        self._render_revenue_chart()
        self._load_notifications()

    def _render_revenue_chart(self) -> None:
        invoices = invoice_service.list()
        recent_days = [(datetime.today() - timedelta(days=i)).date() for i in range(6, -1, -1)]
        revenue = []
        for day in recent_days:
            total = 0.0
            for invoice in invoices:
                if invoice.issued_at.date() == day:
                    total += invoice.total
            revenue.append(total)
        self._axes.clear()
        self._axes.plot([day.strftime("%d.%m") for day in recent_days], revenue, marker="o")
        self._axes.set_ylabel("CZK")
        self._axes.grid(True, axis="y", linestyle="--", alpha=0.4)
        self._figure.tight_layout()
        if self._canvas:
            self._canvas.draw()

    def _load_notifications(self) -> None:
        notifications = sync_service.unread_notifications()
        self._notifications_list.delete(0, tk.END)
        for notification in notifications:
            self._notifications_list.insert(tk.END, f"{notification.title}: {notification.message}")

    def update_language(self) -> None:
        for key, label in self._stats_labels.items():
            parent = label.master
            if isinstance(parent, ttk.Frame):
                parent.winfo_children()[0].config(text=i18n.translate(f"dashboard.{key}"))
        self.refresh()
