from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ...i18n.localization import i18n
from ...models.dto import CustomerDTO
from ...services.customer_service import customer_service
from ...utils.logger import get_logger


class CustomerView(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=24)
        self._logger = get_logger("CustomerView")
        self._search_var = tk.StringVar()
        self._tree = ttk.Treeview(self, columns=("name", "phone", "email"), show="headings")
        self._create_layout()
        self.refresh()

    def _create_layout(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 12))
        add_button = ttk.Button(toolbar, text=i18n.translate("customers.add"), command=self._open_create_dialog)
        add_button.pack(side="left")

        self._undo_button = ttk.Button(toolbar, text=i18n.translate("customers.undo"), command=self._undo)
        self._undo_button.pack(side="left", padx=(8, 0))
        self._redo_button = ttk.Button(toolbar, text=i18n.translate("customers.redo"), command=self._redo)
        self._redo_button.pack(side="left", padx=(8, 0))

        search_entry = ttk.Entry(toolbar, textvariable=self._search_var)
        search_entry.pack(side="right", padx=(0, 8))
        search_entry.bind("<Return>", lambda event: self._search())
        search_label = ttk.Label(toolbar, text=i18n.translate("customers.search"))
        search_label.pack(side="right", padx=(0, 8))

        for col, key in zip(("name", "phone", "email"), ("customers.name", "customers.phone", "customers.email")):
            self._tree.heading(col, text=i18n.translate(key))
            self._tree.column(col, width=200 if col == "name" else 150)
        self._tree.pack(fill="both", expand=True)

    def _open_create_dialog(self) -> None:
        dialog = CustomerDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            try:
                customer_service.create(dialog.result)
                self.refresh()
            except Exception as exc:  # pragma: no cover - UI feedback
                messagebox.showerror("Carixon", str(exc))

    def refresh(self) -> None:
        for row in self._tree.get_children():
            self._tree.delete(row)
        customers = customer_service.list()
        for customer in customers:
            self._tree.insert("", "end", iid=str(customer.id), values=(customer.full_name, customer.phone, customer.email or ""))

    def _search(self) -> None:
        phrase = self._search_var.get().strip()
        if not phrase:
            self.refresh()
            return
        try:
            results = customer_service.search(phrase)
        except Exception as exc:  # pragma: no cover - UI feedback
            messagebox.showerror("Carixon", str(exc))
            return
        for row in self._tree.get_children():
            self._tree.delete(row)
        for customer in results:
            self._tree.insert("", "end", iid=str(customer.id), values=(customer.full_name, customer.phone, customer.email or ""))

    def update_language(self) -> None:
        for col, key in zip(("name", "phone", "email"), ("customers.name", "customers.phone", "customers.email")):
            self._tree.heading(col, text=i18n.translate(key))
        self.refresh()
        for button, key in ((self._undo_button, "customers.undo"), (self._redo_button, "customers.redo")):
            button.config(text=i18n.translate(key))

    def _undo(self) -> None:
        customer_service.undo()
        self.refresh()

    def _redo(self) -> None:
        customer_service.redo()
        self.refresh()


class CustomerDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title(i18n.translate("customers.add"))
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.result: CustomerDTO | None = None
        self._inputs: dict[str, tk.Entry] = {}
        self._build_form()

    def _build_form(self) -> None:
        fields = [
            ("first_name", "customers.first_name"),
            ("last_name", "customers.last_name"),
            ("phone", "customers.phone"),
            ("email", "customers.email"),
        ]
        for index, (key, label_key) in enumerate(fields):
            label = ttk.Label(self, text=i18n.translate(label_key))
            label.grid(row=index, column=0, sticky="w", padx=12, pady=6)
            entry = ttk.Entry(self)
            entry.grid(row=index, column=1, padx=12, pady=6)
            self._inputs[key] = entry
        button = ttk.Button(self, text=i18n.translate("settings.save"), command=self._on_submit)
        button.grid(row=len(fields), column=0, columnspan=2, pady=12)

    def _on_submit(self) -> None:
        first_name = self._inputs["first_name"].get().strip()
        last_name = self._inputs["last_name"].get().strip()
        phone = self._inputs["phone"].get().strip()
        email = self._inputs["email"].get().strip() or None
        if not first_name or not last_name or not phone:
            messagebox.showwarning("Carixon", i18n.translate("customers.validation_required"))
            return
        self.result = CustomerDTO(first_name=first_name, last_name=last_name, phone=phone, email=email)
        self.destroy()
