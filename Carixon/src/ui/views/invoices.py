from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime, timedelta

from ...i18n.localization import i18n
from ...models.dto import InvoiceDTO, InvoiceItemDTO
from ...services.invoice_service import invoice_service


class InvoicesView(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=24)
        self._tree = ttk.Treeview(self, columns=("number", "status", "total"), show="headings")
        self._create_layout()
        self.refresh()

    def _create_layout(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 12))
        add_button = ttk.Button(toolbar, text=i18n.translate("invoices.add"), command=self._open_create_dialog)
        add_button.pack(side="left")

        for col, key in zip(("number", "status", "total"), ("invoices.number", "invoices.status", "invoices.total")):
            self._tree.heading(col, text=i18n.translate(key))
            self._tree.column(col, width=180 if col == "number" else 120)
        self._tree.pack(fill="both", expand=True)

    def refresh(self) -> None:
        for row in self._tree.get_children():
            self._tree.delete(row)
        for invoice in invoice_service.list():
            self._tree.insert(
                "",
                "end",
                iid=str(invoice.id),
                values=(invoice.number, invoice.status, f"{invoice.total:.2f}"),
            )

    def _open_create_dialog(self) -> None:
        dialog = InvoiceDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            try:
                invoice_service.create(dialog.result)
                self.refresh()
            except Exception as exc:
                messagebox.showerror("Carixon", str(exc))

    def update_language(self) -> None:
        for col, key in zip(("number", "status", "total"), ("invoices.number", "invoices.status", "invoices.total")):
            self._tree.heading(col, text=i18n.translate(key))
        self.refresh()


class InvoiceDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title(i18n.translate("invoices.add"))
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.result: InvoiceDTO | None = None
        self._number_var = tk.StringVar()
        self._total_var = tk.StringVar(value="0")
        self._build_form()

    def _build_form(self) -> None:
        ttk.Label(self, text=i18n.translate("invoices.number")).grid(row=0, column=0, sticky="w", padx=12, pady=6)
        ttk.Entry(self, textvariable=self._number_var).grid(row=0, column=1, padx=12, pady=6)
        ttk.Label(self, text=i18n.translate("invoices.total")).grid(row=1, column=0, sticky="w", padx=12, pady=6)
        ttk.Entry(self, textvariable=self._total_var).grid(row=1, column=1, padx=12, pady=6)
        ttk.Button(self, text=i18n.translate("settings.save"), command=self._on_submit).grid(row=2, column=0, columnspan=2, pady=12)

    def _on_submit(self) -> None:
        number = self._number_var.get().strip()
        total = float(self._total_var.get() or 0)
        if not number:
            messagebox.showwarning("Carixon", i18n.translate("invoices.missing_number"))
            return
        issued_at = datetime.utcnow()
        due_at = issued_at + timedelta(days=14)
        self.result = InvoiceDTO(
            number=number,
            due_at=due_at,
            items=[InvoiceItemDTO(name="Service", quantity=1, unit_price=total)],
            status="issued",
        )
        self.destroy()
