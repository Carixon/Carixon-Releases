from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ...i18n.localization import i18n
from ...models.dto import OrderDTO, OrderItemDTO
from ...services.order_service import order_service


class OrdersView(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=24)
        self._tree = ttk.Treeview(self, columns=("title", "status", "total"), show="headings")
        self._create_layout()
        self.refresh()

    def _create_layout(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 12))
        add_button = ttk.Button(toolbar, text=i18n.translate("orders.add"), command=self._open_create_dialog)
        add_button.pack(side="left")

        for col, key in zip(("title", "status", "total"), ("orders.title", "orders.status", "orders.total")):
            self._tree.heading(col, text=i18n.translate(key))
            self._tree.column(col, width=200 if col == "title" else 120)
        self._tree.pack(fill="both", expand=True)

    def refresh(self) -> None:
        for row in self._tree.get_children():
            self._tree.delete(row)
        for order in order_service.list():
            self._tree.insert(
                "",
                "end",
                iid=str(order.id),
                values=(order.title, order.status, f"{order.total:.2f}"),
            )

    def _open_create_dialog(self) -> None:
        dialog = OrderDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            order_service.create(dialog.result)
            self.refresh()

    def update_language(self) -> None:
        for col, key in zip(("title", "status", "total"), ("orders.title", "orders.status", "orders.total")):
            self._tree.heading(col, text=i18n.translate(key))
        self.refresh()


class OrderDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title(i18n.translate("orders.add"))
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.result: OrderDTO | None = None
        self._title_var = tk.StringVar()
        self._total_var = tk.StringVar(value="0")
        self._build_form()

    def _build_form(self) -> None:
        ttk.Label(self, text=i18n.translate("orders.title")).grid(row=0, column=0, sticky="w", padx=12, pady=6)
        ttk.Entry(self, textvariable=self._title_var).grid(row=0, column=1, padx=12, pady=6)
        ttk.Label(self, text=i18n.translate("orders.total")).grid(row=1, column=0, sticky="w", padx=12, pady=6)
        ttk.Entry(self, textvariable=self._total_var).grid(row=1, column=1, padx=12, pady=6)
        ttk.Button(self, text=i18n.translate("settings.save"), command=self._on_submit).grid(row=2, column=0, columnspan=2, pady=12)

    def _on_submit(self) -> None:
        title = self._title_var.get().strip()
        total = float(self._total_var.get() or 0)
        if not title:
            messagebox.showwarning("Carixon", i18n.translate("orders.missing_title"))
            return
        self.result = OrderDTO(title=title, total=total, items=[OrderItemDTO(name=title, quantity=1, unit_price=total)])
        self.destroy()
