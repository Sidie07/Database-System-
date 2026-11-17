# ui.py
# Tkinter user interface for the Logistics Management System.
# Contains: login window, main app shell, and one page per section.

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import hashlib, secrets

# ── Colours and font ──────────────────────────────────────────────────────────
BG       = "#f0f2f5"   # light grey background
SIDEBAR  = "#1b2a3b"   # dark navy sidebar
WHITE    = "#ffffff"
BLUE     = "#2563eb"   # main accent colour
GREEN    = "#16a34a"
RED      = "#dc2626"
ORANGE   = "#d97706"
GREY     = "#6b7280"
TXT      = "#111827"   # dark text
TXT2     = "#4b5563"   # secondary text

FONT = "Segoe UI"

def F(size=10, bold=False):
    """Shorthand for building a font tuple."""
    return (FONT, size, "bold" if bold else "normal")

def btn(parent, text, cmd, bg=BLUE, fg="white", **kw):
    """Creates a flat button with consistent styling."""
    return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                     font=F(9), relief="flat", padx=10, pady=5,
                     activebackground=bg, cursor="hand2", **kw)

def label_entry(frame, text, row, secret=False):
    """Adds a label + entry pair in a grid layout. Returns the StringVar."""
    tk.Label(frame, text=text, font=F(9), bg=WHITE, fg=TXT2).grid(
        row=row, column=0, sticky="w", pady=3)
    var = tk.StringVar()
    tk.Entry(frame, textvariable=var, show="*" if secret else "",
             font=F(9), relief="solid", bd=1, width=26).grid(
        row=row, column=1, sticky="ew", pady=3, padx=(8, 0))
    return var

def make_table(parent, cols):
    """Creates a scrollable Treeview table. Returns the Treeview widget."""
    frame = tk.Frame(parent, bg=WHITE)
    frame.pack(fill="both", expand=True, padx=8, pady=8)

    style = ttk.Style()
    style.configure("Treeview", font=F(9), rowheight=24, background=WHITE,
                    foreground=TXT, fieldbackground=WHITE)
    style.configure("Treeview.Heading", font=F(8, bold=True), background="#f3f4f6")
    style.map("Treeview", background=[("selected", BLUE)],
              foreground=[("selected", "white")])

    vsb = ttk.Scrollbar(frame, orient="vertical")
    tv = ttk.Treeview(frame, columns=cols, show="headings",
                      yscrollcommand=vsb.set, height=16)
    vsb.config(command=tv.yview)
    vsb.pack(side="right", fill="y")
    tv.pack(fill="both", expand=True)

    for c in cols:
        tv.heading(c, text=c)
        tv.column(c, width=max(90, len(c) * 10), minwidth=60)
    return tv

def clear_table(tv):
    """Removes all rows from a Treeview."""
    for row in tv.get_children():
        tv.delete(row)


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class LoginWindow(tk.Toplevel):
    """
    Simple login popup shown before the main window opens.
    Calls controller.authenticate() with the entered username and password.
    """
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self.title("Login")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self.geometry("340x280")
        self._build()

    def _build(self):
        # Title at the top
        tk.Label(self, text="📦 Logistics Hub", font=F(14, bold=True),
                 bg=SIDEBAR, fg="white").pack(fill="x", pady=(0, 16), ipady=14)

        # Form card
        card = tk.Frame(self, bg=WHITE, padx=24, pady=16)
        card.pack(padx=20, fill="both", expand=True)
        card.columnconfigure(1, weight=1)

        self.username = label_entry(card, "Username:", 0)
        self.password = label_entry(card, "Password:", 1, secret=True)

        # Error message label (hidden until login fails)
        self.err = tk.Label(card, text="", font=F(8), bg=WHITE, fg=RED)
        self.err.grid(row=2, columnspan=2, sticky="w")

        btn(card, "Sign In", self._login).grid(row=3, columnspan=2,
                                                sticky="ew", pady=(10, 0))
        self.bind("<Return>", lambda e: self._login())

        tk.Label(self, text="Default: admin / Admin@1234",
                 font=F(8), bg=BG, fg=GREY).pack(pady=6)

    def _login(self):
        u = self.username.get().strip()
        p = self.password.get()
        if not u or not p:
            self.err.config(text="Please fill in both fields.")
            return
        if self.controller.authenticate(u, p):
            self.destroy()   # success — close login, main window will open
        else:
            self.err.config(text="Incorrect username or password.")
            self.password.set("")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class Application(tk.Tk):
    """
    The main window. Built in three parts:
    1. Top bar  — app title and logout button
    2. Sidebar  — navigation buttons for each section
    3. Content  — one page frame per section, stacked; the selected one is raised
    """
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.withdraw()   # hide the window until login succeeds
        self.title("Logistics Management System")
        self.configure(bg=BG)
        self.geometry("1100x680")
        self.minsize(900, 580)

        # Show login first; wait for it to close before continuing
        login = LoginWindow(self, controller)
        self.wait_window(login)

        if not controller.session.is_authenticated():
            self.destroy()
            return

        self._pages = {}
        self._build_topbar()
        self._build_body()
        self.deiconify()   # show the main window now
        self._show("Dashboard")

    # ── Top bar ───────────────────────────────────────────────────────────────

    def _build_topbar(self):
        bar = tk.Frame(self, bg=WHITE, height=46)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(bar, text="📦  Logistics Management System",
                 font=F(11, bold=True), bg=WHITE, fg=TXT).pack(side="left", padx=14)

        btn(bar, "Logout", self._logout, bg=RED).pack(side="right", padx=8, pady=6)

        user = self.controller.session.username or ""
        role = (self.controller.session.role or "").title()
        tk.Label(bar, text=f"👤 {user} ({role})",
                 font=F(9), bg=WHITE, fg=TXT2).pack(side="right", padx=4)

        tk.Frame(self, bg="#e5e7eb", height=1).pack(fill="x")  # divider line

    # ── Body = sidebar + content area ─────────────────────────────────────────

    def _build_body(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        # Sidebar (left column)
        self.sidebar = tk.Frame(body, bg=SIDEBAR, width=180)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Content area (right, fills remaining space)
        self.content = tk.Frame(body, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self._build_pages()

    def _build_sidebar(self):
        """Creates one navigation button per page in the sidebar."""
        is_manager = self.controller.session.has_role("manager")

        # List of (page name, emoji icon) — manager-only pages excluded if needed
        pages = [
            ("Dashboard",  "🏠"),
            ("Shipments",  "📦"),
            ("Deliveries", "🚚"),
            ("Customers",  "👥"),
            ("Inventory",  "🏗️"),
            ("Vehicles",   "🚛"),
            ("Drivers",    "🪪"),
            ("Incidents",  "⚠️"),
            ("Reports",    "📊"),
        ]
        if is_manager:
            pages += [("Users", "🔐"), ("Audit Log", "📋")]

        tk.Label(self.sidebar, text="MENU", font=F(7, bold=True),
                 bg=SIDEBAR, fg="#64748b").pack(anchor="w", padx=14, pady=(12, 4))

        self._nav_btns = {}
        for name, icon in pages:
            b = tk.Button(self.sidebar, text=f"  {icon}  {name}",
                          font=F(9), anchor="w", relief="flat", bd=0,
                          bg=SIDEBAR, fg="#cbd5e1", activebackground="#243447",
                          cursor="hand2", pady=8,
                          command=lambda n=name: self._show(n))
            b.pack(fill="x", padx=4)
            self._nav_btns[name] = b

    def _build_pages(self):
        """Instantiates each page and stacks them in the content area."""
        page_classes = {
            "Dashboard":  DashboardPage,
            "Shipments":  ShipmentsPage,
            "Deliveries": DeliveriesPage,
            "Customers":  CustomersPage,
            "Inventory":  InventoryPage,
            "Vehicles":   VehiclesPage,
            "Drivers":    DriversPage,
            "Incidents":  IncidentsPage,
            "Reports":    ReportsPage,
            "Users":      UsersPage,
            "Audit Log":  AuditLogPage,
        }
        for name, cls in page_classes.items():
            page = cls(self.content, self.controller)
            page.place(relwidth=1, relheight=1)
            self._pages[name] = page

    def _show(self, name):
        """Raises the selected page and highlights its sidebar button."""
        for n, b in self._nav_btns.items():
            b.config(bg=BLUE if n == name else SIDEBAR,
                     fg="white" if n == name else "#cbd5e1")
        page = self._pages.get(name)
        if page:
            page.tkraise()
            if hasattr(page, "refresh"):
                page.refresh()

    def _logout(self):
        if messagebox.askyesno("Logout", "Log out and close?"):
            self.controller.logout()
            self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# BASE PAGE — all pages inherit from this
# ══════════════════════════════════════════════════════════════════════════════

class BasePage(tk.Frame):
    """
    Shared base for every page.
    Provides: page heading, a shortcut to the database, and helper methods
    for building buttons and tables consistently.
    """
    def __init__(self, parent, controller, title):
        super().__init__(parent, bg=BG)
        self.controller = controller
        self.db = controller.db

        # Page heading
        tk.Label(self, text=title, font=F(14, bold=True),
                 bg=BG, fg=TXT).pack(anchor="w", padx=20, pady=(14, 6))

    def action_bar(self):
        """Returns a Frame used as a toolbar at the top of a page."""
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=16, pady=4)
        return bar

    def table_frame(self):
        """Returns a white card frame that holds a table."""
        f = tk.Frame(self, bg=WHITE)
        f.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        return f

    def refresh(self):
        pass  # overridden by subclasses that need to reload data


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

class DashboardPage(BasePage):
    """Shows key stats at a glance: shipment counts, vehicles, incidents, etc."""

    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Dashboard")
        # Grid for stat boxes
        self.grid_frame = tk.Frame(self, bg=BG)
        self.grid_frame.pack(fill="x", padx=16)

        # Low-stock alert table below the stats
        tk.Label(self, text="⚠️ Low Stock Items", font=F(10, bold=True),
                 bg=BG, fg=TXT).pack(anchor="w", padx=16, pady=(8, 2))
        f = self.table_frame()
        self.stock_tv = make_table(f, ["SKU", "Name", "Qty", "Reorder Level", "Warehouse"])

    def refresh(self):
        # Clear old stat boxes
        for w in self.grid_frame.winfo_children():
            w.destroy()

        try:
            s = self.db.get_dashboard_stats()
        except Exception:
            return

        # Each tuple: (label, value, colour)
        stats = [
            ("Total Shipments",    s["total_shipments"],    BLUE),
            ("Active Deliveries",  s["active_deliveries"],  "#7c3aed"),
            ("Delivered Today",    s["delivered_today"],    GREEN),
            ("Available Vehicles", s["available_vehicles"], "#0891b2"),
            ("Available Drivers",  s["available_drivers"],  "#0d9488"),
            ("Open Incidents",     s["open_incidents"],     RED),
            ("Low Stock Items",    s["low_stock_items"],    ORANGE),
            ("Revenue (Month)",    f"£{s['revenue_this_month']:,.0f}", "#1d4ed8"),
        ]

        cols = 4
        for i, (title, value, colour) in enumerate(stats):
            self.grid_frame.columnconfigure(i % cols, weight=1)
            card = tk.Frame(self.grid_frame, bg=colour, padx=16, pady=12)
            card.grid(row=i // cols, column=i % cols, padx=6, pady=6, sticky="nsew")
            tk.Label(card, text=str(value), font=F(18, bold=True),
                     bg=colour, fg="white").pack(anchor="w")
            tk.Label(card, text=title, font=F(9), bg=colour, fg="white").pack(anchor="w")

        # Low stock table
        clear_table(self.stock_tv)
        for item in self.db.get_low_stock_items():
            self.stock_tv.insert("", "end", values=(
                item.get("sku"), item.get("name"),
                item.get("quantity"), item.get("reorder_level"),
                item.get("warehouse_name")))


# ══════════════════════════════════════════════════════════════════════════════
# SHIPMENTS
# ══════════════════════════════════════════════════════════════════════════════

class ShipmentsPage(BasePage):
    """View all shipments, create new ones, update status, mark as paid."""

    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Shipments")

        bar = self.action_bar()
        btn(bar, "+ New Shipment", self._new).pack(side="left", padx=(0, 6))
        btn(bar, "Update Status", self._update_status, bg=ORANGE).pack(side="left", padx=(0, 6))
        btn(bar, "Mark Paid", self._mark_paid, bg=GREEN).pack(side="left", padx=(0, 6))
        btn(bar, "↻ Refresh", self.refresh, bg=GREY).pack(side="left")

        # Status filter
        tk.Label(bar, text="  Filter:", font=F(9), bg=BG, fg=TXT2).pack(side="left")
        self.filter_var = tk.StringVar(value="All")
        cb = ttk.Combobox(bar, textvariable=self.filter_var, width=14, state="readonly",
                          values=["All","pending","in_transit","delivered","delayed","cancelled"])
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        f = self.table_frame()
        self.tv = make_table(f, ["ID","Tracking","Sender","Receiver","Weight kg","Status","Priority","Payment","Date"])

    def refresh(self):
        clear_table(self.tv)
        status = self.filter_var.get()
        rows = self.db.get_all_shipments(status="" if status == "All" else status)
        for r in rows:
            self.tv.insert("", "end", iid=str(r["shipment_id"]), values=(
                r["shipment_id"], r["tracking_number"],
                r.get("sender_name","—"), r.get("receiver_name","—"),
                r.get("weight_kg", 0), r["status"].replace("_"," ").title(),
                r["priority"].title(), r["payment_status"].title(),
                str(r["created_at"])[:10]))

    def _selected(self):
        sel = self.tv.selection()
        return int(sel[0]) if sel else None

    def _new(self):
        """Opens a simple dialog to create a new shipment."""
        customers = self.db.get_all_customers()
        names = [f"{c['customer_id']} — {c['name']}" for c in customers]

        dlg = tk.Toplevel(self)
        dlg.title("New Shipment")
        dlg.configure(bg=WHITE)
        dlg.geometry("400x420")
        dlg.grab_set()
        f = tk.Frame(dlg, bg=WHITE, padx=20, pady=16)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        # Sender dropdown
        tk.Label(f, text="Sender:", font=F(9), bg=WHITE, fg=TXT2).grid(row=0, column=0, sticky="w", pady=4)
        sender_var = tk.StringVar()
        ttk.Combobox(f, textvariable=sender_var, values=names, state="readonly").grid(
            row=0, column=1, sticky="ew", pady=4, padx=(8,0))

        # Receiver dropdown
        tk.Label(f, text="Receiver:", font=F(9), bg=WHITE, fg=TXT2).grid(row=1, column=0, sticky="w", pady=4)
        recv_var = tk.StringVar()
        ttk.Combobox(f, textvariable=recv_var, values=names, state="readonly").grid(
            row=1, column=1, sticky="ew", pady=4, padx=(8,0))

        desc   = label_entry(f, "Description:", 2)
        weight = label_entry(f, "Weight (kg):", 3)
        cost   = label_entry(f, "Shipping Cost (£):", 4)

        tk.Label(f, text="Priority:", font=F(9), bg=WHITE, fg=TXT2).grid(row=5, column=0, sticky="w", pady=4)
        pri_var = tk.StringVar(value="standard")
        ttk.Combobox(f, textvariable=pri_var, state="readonly",
                     values=["standard","express","overnight"]).grid(
            row=5, column=1, sticky="ew", pady=4, padx=(8,0))

        def save():
            sid = int(sender_var.get().split("—")[0]) if sender_var.get() else None
            rid = int(recv_var.get().split("—")[0]) if recv_var.get() else None
            if not sid or not rid:
                messagebox.showwarning("Missing", "Select sender and receiver.", parent=dlg)
                return
            try:
                _, tracking = self.db.create_shipment(
                    sender_id=sid, receiver_id=rid,
                    description=desc.get(),
                    weight_kg=float(weight.get() or 0),
                    shipping_cost=float(cost.get() or 0),
                    priority=pri_var.get(),
                    created_by=self.controller.session.username)
                messagebox.showinfo("Created", f"Tracking: {tracking}", parent=dlg)
                self.refresh()
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        btn(dlg, "Create", save).pack(pady=10)

    def _update_status(self):
        sid = self._selected()
        if not sid:
            messagebox.showwarning("Select", "Select a shipment first.")
            return
        new = simpledialog.askstring("Status",
            "New status:\npending / in_transit / delivered / delayed / cancelled", parent=self)
        if new:
            self.db.update_shipment_status(sid, new.strip())
            self.refresh()

    def _mark_paid(self):
        sid = self._selected()
        if not sid:
            messagebox.showwarning("Select", "Select a shipment first.")
            return
        self.db.update_shipment(sid, payment_status="paid")
        self.refresh()


# ══════════════════════════════════════════════════════════════════════════════
# DELIVERIES
# ══════════════════════════════════════════════════════════════════════════════

class DeliveriesPage(BasePage):
    """Assign shipments to drivers and vehicles, then dispatch and complete them."""

    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Deliveries")

        bar = self.action_bar()
        btn(bar, "+ Assign", self._assign).pack(side="left", padx=(0,6))
        btn(bar, "Dispatch", self._dispatch, bg=GREEN).pack(side="left", padx=(0,6))
        btn(bar, "Complete", self._complete, bg="#0891b2").pack(side="left", padx=(0,6))
        btn(bar, "Fail", self._fail, bg=RED).pack(side="left", padx=(0,6))
        btn(bar, "↻ Refresh", self.refresh, bg=GREY).pack(side="left")

        f = self.table_frame()
        self.tv = make_table(f, ["ID","Shipment","Tracking","Driver","Vehicle","Scheduled","Status"])

    def refresh(self):
        clear_table(self.tv)
        rows = self.db.execute_query("""
            SELECT d.delivery_id, d.shipment_id, s.tracking_number,
                   dr.full_name, v.registration, d.scheduled_date, d.delivery_status
            FROM deliveries d
            JOIN shipments s ON d.shipment_id = s.shipment_id
            LEFT JOIN drivers dr ON d.driver_id = dr.driver_id
            LEFT JOIN vehicles v  ON d.vehicle_id = v.vehicle_id
            ORDER BY d.delivery_id DESC LIMIT 200
        """)
        for r in rows:
            self.tv.insert("", "end", iid=str(r["delivery_id"]), values=(
                r["delivery_id"], r["shipment_id"], r.get("tracking_number",""),
                r.get("full_name","—"), r.get("registration","—"),
                str(r.get("scheduled_date","") or "")[:10],
                r.get("delivery_status","").replace("_"," ").title()))

    def _selected(self):
        sel = self.tv.selection()
        return int(sel[0]) if sel else None

    def _assign(self):
        """Opens a popup to link a shipment to a driver + vehicle."""
        pending  = self.db.get_all_shipments(status="pending")
        drivers  = self.db.get_available_drivers()
        vehicles = self.db.get_available_vehicles()

        dlg = tk.Toplevel(self)
        dlg.title("Assign Delivery")
        dlg.configure(bg=WHITE)
        dlg.geometry("380x300")
        dlg.grab_set()
        f = tk.Frame(dlg, bg=WHITE, padx=20, pady=14)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        def row_label(text, r):
            tk.Label(f, text=text, font=F(9), bg=WHITE, fg=TXT2).grid(
                row=r, column=0, sticky="w", pady=5)

        row_label("Shipment:", 0)
        ship_var = tk.StringVar()
        ttk.Combobox(f, textvariable=ship_var, state="readonly",
                     values=[f"{s['shipment_id']} — {s['tracking_number']}" for s in pending]
                     ).grid(row=0, column=1, sticky="ew", padx=(8,0))

        row_label("Driver:", 1)
        drv_var = tk.StringVar()
        ttk.Combobox(f, textvariable=drv_var, state="readonly",
                     values=[f"{d['driver_id']} — {d['full_name']}" for d in drivers]
                     ).grid(row=1, column=1, sticky="ew", padx=(8,0))

        row_label("Vehicle:", 2)
        veh_var = tk.StringVar()
        ttk.Combobox(f, textvariable=veh_var, state="readonly",
                     values=[f"{v['vehicle_id']} — {v['registration']}" for v in vehicles]
                     ).grid(row=2, column=1, sticky="ew", padx=(8,0))

        sched = label_entry(f, "Scheduled Date\n(YYYY-MM-DD):", 3)

        def save():
            sid = int(ship_var.get().split("—")[0]) if ship_var.get() else None
            did = int(drv_var.get().split("—")[0]) if drv_var.get() else None
            vid = int(veh_var.get().split("—")[0]) if veh_var.get() else None
            if not sid:
                messagebox.showwarning("Missing", "Select a shipment.", parent=dlg)
                return
            try:
                self.db.create_delivery(shipment_id=sid, driver_id=did,
                                        vehicle_id=vid, scheduled_date=sched.get())
                self.refresh()
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        btn(dlg, "Assign", save).pack(pady=10)

    def _dispatch(self):
        did = self._selected()
        if not did:
            messagebox.showwarning("Select", "Select a delivery first.")
            return
        try:
            self.db.dispatch_delivery(did)
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _complete(self):
        did = self._selected()
        if not did:
            messagebox.showwarning("Select", "Select a delivery first.")
            return
        name = simpledialog.askstring("Recipient", "Recipient name:", parent=self) or ""
        try:
            self.db.complete_delivery(did, recipient_name=name)
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _fail(self):
        did = self._selected()
        if not did:
            messagebox.showwarning("Select", "Select a delivery first.")
            return
        reason = simpledialog.askstring("Reason", "Failure reason:", parent=self) or ""
        try:
            self.db.fail_delivery(did, reason=reason)
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOMERS
# ══════════════════════════════════════════════════════════════════════════════

class CustomersPage(BasePage):
    """Add and search customer records."""

    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Customers")

        bar = self.action_bar()
        btn(bar, "+ Add Customer", self._add).pack(side="left", padx=(0,6))

        tk.Label(bar, text="  Search:", font=F(9), bg=BG, fg=TXT2).pack(side="left")
        self.search_var = tk.StringVar()
        tk.Entry(bar, textvariable=self.search_var, font=F(9), width=20).pack(side="left", padx=4)
        btn(bar, "🔍", self._search, bg=GREY).pack(side="left", padx=(0,4))
        btn(bar, "↻ All", self.refresh, bg=GREY).pack(side="left")

        f = self.table_frame()
        self.tv = make_table(f, ["ID","Name","Email","Phone","City","Country"])

    def refresh(self):
        clear_table(self.tv)
        for r in self.db.get_all_customers():
            self.tv.insert("", "end", values=(
                r["customer_id"], r["name"], r.get("email",""),
                r.get("phone",""), r.get("city",""), r.get("country","UK")))

    def _search(self):
        q = self.search_var.get().strip()
        if not q:
            return self.refresh()
        clear_table(self.tv)
        for r in self.db.search_customers(q):
            self.tv.insert("", "end", values=(
                r["customer_id"], r["name"], r.get("email",""),
                r.get("phone",""), r.get("city",""), r.get("country","UK")))

    def _add(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add Customer")
        dlg.configure(bg=WHITE)
        dlg.geometry("360x280")
        dlg.grab_set()
        f = tk.Frame(dlg, bg=WHITE, padx=20, pady=14)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        name  = label_entry(f, "Name *:", 0)
        email = label_entry(f, "Email:", 1)
        phone = label_entry(f, "Phone:", 2)
        city  = label_entry(f, "City:", 3)

        def save():
            if not name.get():
                messagebox.showwarning("Required", "Name is required.", parent=dlg)
                return
            self.db.create_customer(name=name.get(), email=email.get(),
                                    phone=phone.get(), city=city.get())
            self.refresh()
            dlg.destroy()

        btn(dlg, "Save", save).pack(pady=10)


# ══════════════════════════════════════════════════════════════════════════════
# INVENTORY
# ══════════════════════════════════════════════════════════════════════════════

class InventoryPage(BasePage):
    """View stock levels across warehouses. Add items and adjust quantities."""

    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Inventory")

        bar = self.action_bar()
        btn(bar, "+ Add Item", self._add).pack(side="left", padx=(0,6))
        btn(bar, "Stock In ↑", self._stock_in, bg=GREEN).pack(side="left", padx=(0,6))
        btn(bar, "Stock Out ↓", self._stock_out, bg=ORANGE).pack(side="left", padx=(0,6))
        btn(bar, "↻ Refresh", self.refresh, bg=GREY).pack(side="left")

        f = self.table_frame()
        self.tv = make_table(f, ["ID","SKU","Name","Category","Qty","Reorder","Warehouse"])

    def refresh(self):
        clear_table(self.tv)
        rows = self.db.execute_query(
            "SELECT i.*, w.name AS wname FROM inventory i "
            "JOIN warehouses w ON i.warehouse_id=w.warehouse_id ORDER BY i.name")
        for r in rows:
            # Highlight low-stock rows in light red
            tag = "low" if r["quantity"] <= r["reorder_level"] else ""
            self.tv.insert("", "end", tags=(tag,), values=(
                r["item_id"], r["sku"], r["name"], r.get("category",""),
                r["quantity"], r["reorder_level"], r.get("wname","")))
        self.tv.tag_configure("low", background="#fee2e2")

    def _selected_id(self):
        sel = self.tv.selection()
        return int(self.tv.item(sel[0])["values"][0]) if sel else None

    def _add(self):
        warehouses = self.db.get_all_warehouses()
        wh_map = {w["name"]: w["warehouse_id"] for w in warehouses}

        dlg = tk.Toplevel(self)
        dlg.title("Add Inventory Item")
        dlg.configure(bg=WHITE)
        dlg.geometry("360x280")
        dlg.grab_set()
        f = tk.Frame(dlg, bg=WHITE, padx=20, pady=14)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        sku   = label_entry(f, "SKU *:", 0)
        name  = label_entry(f, "Name *:", 1)
        qty   = label_entry(f, "Quantity:", 2)
        reord = label_entry(f, "Reorder Level:", 3)

        tk.Label(f, text="Warehouse *:", font=F(9), bg=WHITE, fg=TXT2).grid(row=4, column=0, sticky="w")
        wh_var = tk.StringVar()
        ttk.Combobox(f, textvariable=wh_var, values=list(wh_map.keys()),
                     state="readonly").grid(row=4, column=1, sticky="ew", padx=(8,0))

        def save():
            if not sku.get() or not name.get() or not wh_var.get():
                messagebox.showwarning("Required", "SKU, Name and Warehouse required.", parent=dlg)
                return
            self.db.add_inventory_item(
                warehouse_id=wh_map[wh_var.get()], sku=sku.get(), name=name.get(),
                quantity=int(qty.get() or 0), reorder_level=int(reord.get() or 10))
            self.refresh()
            dlg.destroy()

        btn(dlg, "Add", save).pack(pady=10)

    def _stock_in(self):
        self._adjust("IN")

    def _stock_out(self):
        self._adjust("OUT")

    def _adjust(self, direction):
        item_id = self._selected_id()
        if not item_id:
            messagebox.showwarning("Select", "Select an item first.")
            return
        qty = simpledialog.askinteger("Quantity", f"Amount to {'add' if direction=='IN' else 'remove'}:",
                                      parent=self, minvalue=1)
        if qty is None:
            return
        try:
            self.db.update_stock(item_id, qty if direction == "IN" else -qty,
                                 movement_type=direction,
                                 performed_by=self.controller.session.username)
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))


# ══════════════════════════════════════════════════════════════════════════════
# VEHICLES
# ══════════════════════════════════════════════════════════════════════════════

class VehiclesPage(BasePage):
    """Add vehicles to the fleet and update their availability status."""

    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Vehicles")

        bar = self.action_bar()
        btn(bar, "+ Add Vehicle", self._add).pack(side="left", padx=(0,6))
        btn(bar, "Update Status", self._status, bg=ORANGE).pack(side="left", padx=(0,6))
        btn(bar, "↻ Refresh", self.refresh, bg=GREY).pack(side="left")

        f = self.table_frame()
        self.tv = make_table(f, ["ID","Reg","Make","Model","Type","Capacity kg","Status"])

    def refresh(self):
        clear_table(self.tv)
        for r in self.db.get_all_vehicles():
            self.tv.insert("", "end", iid=str(r["vehicle_id"]), values=(
                r["vehicle_id"], r["registration"], r["make"], r["model"],
                r["vehicle_type"], r.get("capacity_kg",""),
                r["status"].replace("_"," ").title()))

    def _selected(self):
        sel = self.tv.selection()
        return int(sel[0]) if sel else None

    def _add(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add Vehicle")
        dlg.configure(bg=WHITE)
        dlg.geometry("360x280")
        dlg.grab_set()
        f = tk.Frame(dlg, bg=WHITE, padx=20, pady=14)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        reg  = label_entry(f, "Registration *:", 0)
        make = label_entry(f, "Make *:", 1)
        model = label_entry(f, "Model *:", 2)
        cap  = label_entry(f, "Capacity (kg) *:", 3)

        tk.Label(f, text="Type *:", font=F(9), bg=WHITE, fg=TXT2).grid(row=4, column=0, sticky="w")
        type_var = tk.StringVar(value="van")
        ttk.Combobox(f, textvariable=type_var, state="readonly",
                     values=["van","truck","lorry","motorbike","car"]).grid(
            row=4, column=1, sticky="ew", padx=(8,0))

        def save():
            if not reg.get() or not make.get() or not cap.get():
                messagebox.showwarning("Required", "Registration, Make and Capacity required.", parent=dlg)
                return
            self.db.add_vehicle(registration=reg.get(), make=make.get(),
                                model=model.get(), vehicle_type=type_var.get(),
                                capacity_kg=float(cap.get()))
            self.refresh()
            dlg.destroy()

        btn(dlg, "Add Vehicle", save).pack(pady=10)

    def _status(self):
        vid = self._selected()
        if not vid:
            messagebox.showwarning("Select", "Select a vehicle first.")
            return
        new = simpledialog.askstring("Status",
            "New status: available / in_use / maintenance / retired", parent=self)
        if new:
            self.db.update_vehicle_status(vid, new.strip())
            self.refresh()


# ══════════════════════════════════════════════════════════════════════════════
# DRIVERS
# ══════════════════════════════════════════════════════════════════════════════

class DriversPage(BasePage):
    """Add driver records with licence details and update their shift status."""

    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Drivers")

        bar = self.action_bar()
        btn(bar, "+ Add Driver", self._add).pack(side="left", padx=(0,6))
        btn(bar, "Update Status", self._status, bg=ORANGE).pack(side="left", padx=(0,6))
        btn(bar, "↻ Refresh", self.refresh, bg=GREY).pack(side="left")

        f = self.table_frame()
        self.tv = make_table(f, ["ID","Name","Licence No.","Expiry","Phone","Status"])

    def refresh(self):
        clear_table(self.tv)
        for r in self.db.get_all_drivers():
            self.tv.insert("", "end", iid=str(r["driver_id"]), values=(
                r["driver_id"], r["full_name"], r.get("licence_number",""),
                str(r.get("licence_expiry",""))[:10], r.get("phone",""),
                r.get("status","").replace("_"," ").title()))

    def _selected(self):
        sel = self.tv.selection()
        return int(sel[0]) if sel else None

    def _add(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add Driver")
        dlg.configure(bg=WHITE)
        dlg.geometry("360x260")
        dlg.grab_set()
        f = tk.Frame(dlg, bg=WHITE, padx=20, pady=14)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        name    = label_entry(f, "Full Name *:", 0)
        licence = label_entry(f, "Licence No. *:", 1)
        expiry  = label_entry(f, "Expiry (YYYY-MM-DD):", 2)
        phone   = label_entry(f, "Phone:", 3)

        def save():
            if not name.get() or not licence.get():
                messagebox.showwarning("Required", "Name and Licence No. required.", parent=dlg)
                return
            self.db.add_driver(full_name=name.get(), licence_number=licence.get(),
                               licence_expiry=expiry.get() or "N/A", phone=phone.get())
            self.refresh()
            dlg.destroy()

        btn(dlg, "Add Driver", save).pack(pady=10)

    def _status(self):
        did = self._selected()
        if not did:
            messagebox.showwarning("Select", "Select a driver first.")
            return
        new = simpledialog.askstring("Status",
            "New status: available / on_route / off_duty / suspended", parent=self)
        if new:
            self.db.update_driver_status(did, new.strip())
            self.refresh()


# ══════════════════════════════════════════════════════════════════════════════
# INCIDENTS
# ══════════════════════════════════════════════════════════════════════════════

class IncidentsPage(BasePage):
    """Log issues (delays, damages, failed deliveries) and mark them resolved."""

    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Incidents")

        bar = self.action_bar()
        btn(bar, "+ Log Incident", self._log).pack(side="left", padx=(0,6))
        btn(bar, "✔ Resolve", self._resolve, bg=GREEN).pack(side="left", padx=(0,6))
        btn(bar, "↻ Refresh", self.refresh, bg=GREY).pack(side="left")

        f = self.table_frame()
        self.tv = make_table(f, ["ID","Type","Shipment ID","Description","Reported By","Resolved"])

    def refresh(self):
        clear_table(self.tv)
        for r in self.db.execute_query(
            "SELECT * FROM incidents ORDER BY reported_at DESC LIMIT 200"):
            self.tv.insert("", "end", iid=str(r["incident_id"]), values=(
                r["incident_id"], r["incident_type"].replace("_"," ").title(),
                r.get("shipment_id","—"), str(r.get("description",""))[:50],
                r.get("reported_by",""), "Yes" if r.get("resolved") else "No"))

    def _selected(self):
        sel = self.tv.selection()
        return int(sel[0]) if sel else None

    def _log(self):
        dlg = tk.Toplevel(self)
        dlg.title("Log Incident")
        dlg.configure(bg=WHITE)
        dlg.geometry("360x240")
        dlg.grab_set()
        f = tk.Frame(dlg, bg=WHITE, padx=20, pady=14)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        ship_id = label_entry(f, "Shipment ID:", 0)
        desc    = label_entry(f, "Description *:", 1)

        tk.Label(f, text="Type *:", font=F(9), bg=WHITE, fg=TXT2).grid(row=2, column=0, sticky="w", pady=4)
        type_var = tk.StringVar()
        ttk.Combobox(f, textvariable=type_var, state="readonly",
                     values=["delay","damage","failed_delivery","route_change","lost","other"]
                     ).grid(row=2, column=1, sticky="ew", padx=(8,0))

        def save():
            if not desc.get() or not type_var.get():
                messagebox.showwarning("Required", "Type and description required.", parent=dlg)
                return
            sid = int(ship_id.get()) if ship_id.get().isdigit() else None
            self.db.log_incident(incident_type=type_var.get(), description=desc.get(),
                                 shipment_id=sid,
                                 reported_by=self.controller.session.username)
            self.refresh()
            dlg.destroy()

        btn(dlg, "Log Incident", save, bg=RED).pack(pady=10)

    def _resolve(self):
        iid = self._selected()
        if not iid:
            messagebox.showwarning("Select", "Select an incident first.")
            return
        note = simpledialog.askstring("Resolution", "Resolution note:", parent=self) or ""
        self.db.resolve_incident(iid, resolution_note=note)
        self.refresh()


# ══════════════════════════════════════════════════════════════════════════════
# REPORTS
# ══════════════════════════════════════════════════════════════════════════════

class ReportsPage(BasePage):
    """Summary reports: shipment statuses, vehicle usage, driver activity, revenue."""

    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Reports")

        btn(self.action_bar(), "↻ Refresh All", self.refresh, bg=GREY).pack(side="left")

        # Use a notebook (tabs) so each report has its own view
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=16, pady=8)

        self.tv_delivery = self._add_tab("Delivery Progress", ["Status", "Count"])
        self.tv_vehicles = self._add_tab("Vehicles",    ["Reg","Make","Status","Deliveries"])
        self.tv_drivers  = self._add_tab("Drivers",     ["Name","Status","Deliveries"])
        self.tv_revenue  = self._add_tab("Revenue",     ["Payment Status","Total (£)"])
        self.tv_incident = self._add_tab("Incidents",   ["Type","Total","Resolved","Open"])

    def _add_tab(self, title, cols):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text=title)
        return make_table(tab, cols)

    def refresh(self):
        # Delivery progress
        clear_table(self.tv_delivery)
        for status, count in self.db.report_delivery_progress().items():
            self.tv_delivery.insert("", "end", values=(status.replace("_"," ").title(), count))

        # Vehicle usage
        clear_table(self.tv_vehicles)
        for r in self.db.report_vehicle_usage():
            self.tv_vehicles.insert("", "end", values=(
                r["registration"], r["make"], r["status"], r.get("total_deliveries",0)))

        # Driver activity
        clear_table(self.tv_drivers)
        for r in self.db.report_driver_activity():
            self.tv_drivers.insert("", "end", values=(
                r["full_name"], r["status"], r.get("total_deliveries",0)))

        # Revenue
        clear_table(self.tv_revenue)
        for status, total in self.db.report_revenue().items():
            self.tv_revenue.insert("", "end", values=(status.title(), f"£{total:,.2f}"))

        # Incident summary
        clear_table(self.tv_incident)
        for r in self.db.report_incident_summary():
            self.tv_incident.insert("", "end", values=(
                r["incident_type"].replace("_"," ").title(),
                r["total"], r["resolved"], r["open"]))


# ══════════════════════════════════════════════════════════════════════════════
# USERS  (manager / admin only)
# ══════════════════════════════════════════════════════════════════════════════

class UsersPage(BasePage):
    """Create new user accounts and deactivate existing ones."""

    def __init__(self, parent, controller):
        super().__init__(parent, controller, "User Management")

        bar = self.action_bar()
        btn(bar, "+ New User", self._add).pack(side="left", padx=(0,6))
        btn(bar, "Deactivate", self._deactivate, bg=RED).pack(side="left", padx=(0,6))
        btn(bar, "↻ Refresh", self.refresh, bg=GREY).pack(side="left")

        f = self.table_frame()
        self.tv = make_table(f, ["ID","Username","Full Name","Role","Active"])

    def refresh(self):
        clear_table(self.tv)
        for r in self.db.get_all_users():
            self.tv.insert("", "end", iid=str(r["user_id"]), values=(
                r["user_id"], r["username"], r["full_name"],
                r["role"].title(), "Yes" if r.get("is_active") else "No"))

    def _selected(self):
        sel = self.tv.selection()
        return int(sel[0]) if sel else None

    def _add(self):
        dlg = tk.Toplevel(self)
        dlg.title("New User")
        dlg.configure(bg=WHITE)
        dlg.geometry("360x280")
        dlg.grab_set()
        f = tk.Frame(dlg, bg=WHITE, padx=20, pady=14)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        uname  = label_entry(f, "Username *:", 0)
        fname  = label_entry(f, "Full Name *:", 1)
        passwd = label_entry(f, "Password *:", 2, secret=True)

        tk.Label(f, text="Role *:", font=F(9), bg=WHITE, fg=TXT2).grid(row=3, column=0, sticky="w")
        role_var = tk.StringVar(value="staff")
        ttk.Combobox(f, textvariable=role_var, state="readonly",
                     values=["admin","manager","staff","driver"]).grid(
            row=3, column=1, sticky="ew", padx=(8,0))

        def save():
            if not uname.get() or not fname.get() or not passwd.get():
                messagebox.showwarning("Required", "All fields required.", parent=dlg)
                return
            salt   = secrets.token_hex(16)
            hashed = hashlib.sha256((salt + passwd.get()).encode()).hexdigest()
            try:
                self.db.create_user(username=uname.get(), password_hash=hashed,
                                    salt=salt, role=role_var.get(),
                                    full_name=fname.get(), must_change_pwd=True)
                self.refresh()
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        btn(dlg, "Create User", save).pack(pady=10)

    def _deactivate(self):
        uid = self._selected()
        if not uid:
            messagebox.showwarning("Select", "Select a user first.")
            return
        if uid == self.controller.session.user.get("user_id"):
            messagebox.showwarning("Denied", "Cannot deactivate your own account.")
            return
        if messagebox.askyesno("Confirm", "Deactivate this account?"):
            self.db.deactivate_user(uid)
            self.refresh()


# ══════════════════════════════════════════════════════════════════════════════
# AUDIT LOG  (manager / admin only)
# ══════════════════════════════════════════════════════════════════════════════

class AuditLogPage(BasePage):
    """Read-only view of all recorded system actions (logins, logouts, etc.)."""

    def __init__(self, parent, controller):
        super().__init__(parent, controller, "Audit Log")

        bar = self.action_bar()
        btn(bar, "↻ Refresh", self.refresh, bg=GREY).pack(side="left")

        f = self.table_frame()
        self.tv = make_table(f, ["ID","Action","Actor","Detail","Timestamp"])

    def refresh(self):
        clear_table(self.tv)
        for r in self.db.get_audit_log(limit=300):
            self.tv.insert("", "end", values=(
                r["log_id"], r["action"], r["actor"],
                r.get("detail",""), str(r.get("timestamp",""))[:19]))