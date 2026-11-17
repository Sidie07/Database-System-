"""
database.py — Logistics Management System Database Layer
Manages all SQLite operations: schema creation, CRUD, and reporting.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger("database")


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
-- ── Users & Access Control ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    salt            TEXT    NOT NULL,
    role            TEXT    NOT NULL CHECK(role IN ('admin','manager','staff','driver')),
    full_name       TEXT    NOT NULL,
    email           TEXT,
    phone           TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    must_change_pwd INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Audit Log ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT    NOT NULL,
    actor       TEXT    NOT NULL,
    detail      TEXT,
    timestamp   TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Customers ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customers (
    customer_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    email           TEXT,
    phone           TEXT,
    address         TEXT,
    city            TEXT,
    postcode        TEXT,
    country         TEXT    DEFAULT 'UK',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Warehouses ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS warehouses (
    warehouse_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    address         TEXT    NOT NULL,
    city            TEXT    NOT NULL,
    postcode        TEXT,
    capacity        REAL,                       -- total capacity in cubic metres
    manager_name    TEXT,
    phone           TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1
);

-- ── Inventory ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inventory (
    item_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_id    INTEGER NOT NULL REFERENCES warehouses(warehouse_id),
    sku             TEXT    NOT NULL,
    name            TEXT    NOT NULL,
    description     TEXT,
    category        TEXT,
    quantity        INTEGER NOT NULL DEFAULT 0,
    reorder_level   INTEGER NOT NULL DEFAULT 10,
    unit_weight_kg  REAL,
    location_code   TEXT,                       -- aisle/shelf code within warehouse
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(warehouse_id, sku)
);

-- ── Inventory Movements ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inventory_movements (
    movement_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id         INTEGER NOT NULL REFERENCES inventory(item_id),
    warehouse_id    INTEGER NOT NULL REFERENCES warehouses(warehouse_id),
    movement_type   TEXT    NOT NULL CHECK(movement_type IN ('IN','OUT','TRANSFER','ADJUSTMENT')),
    quantity        INTEGER NOT NULL,
    reference       TEXT,                       -- shipment ID or transfer note
    performed_by    TEXT,
    movement_date   TEXT    NOT NULL DEFAULT (datetime('now')),
    notes           TEXT
);

-- ── Vehicles ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    registration        TEXT    NOT NULL UNIQUE,
    make                TEXT    NOT NULL,
    model               TEXT    NOT NULL,
    year                INTEGER,
    vehicle_type        TEXT    NOT NULL CHECK(vehicle_type IN ('van','truck','lorry','motorbike','car')),
    capacity_kg         REAL    NOT NULL,
    capacity_m3         REAL,
    status              TEXT    NOT NULL DEFAULT 'available'
                                CHECK(status IN ('available','in_use','maintenance','retired')),
    last_service_date   TEXT,
    next_service_date   TEXT,
    mileage_km          REAL    DEFAULT 0,
    notes               TEXT
);

-- ── Drivers ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS drivers (
    driver_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER REFERENCES users(user_id),
    full_name           TEXT    NOT NULL,
    licence_number      TEXT    NOT NULL UNIQUE,
    licence_expiry      TEXT    NOT NULL,
    licence_class       TEXT,
    phone               TEXT,
    email               TEXT,
    shift_start         TEXT,
    shift_end           TEXT,
    status              TEXT    NOT NULL DEFAULT 'available'
                                CHECK(status IN ('available','on_route','off_duty','suspended')),
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Routes ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS routes (
    route_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    origin          TEXT    NOT NULL,
    destination     TEXT    NOT NULL,
    distance_km     REAL,
    estimated_hours REAL,
    notes           TEXT
);

-- ── Shipments ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shipments (
    shipment_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tracking_number     TEXT    NOT NULL UNIQUE,
    sender_id           INTEGER REFERENCES customers(customer_id),
    receiver_id         INTEGER REFERENCES customers(customer_id),
    origin_warehouse    INTEGER REFERENCES warehouses(warehouse_id),
    dest_warehouse      INTEGER REFERENCES warehouses(warehouse_id),
    description         TEXT,
    weight_kg           REAL,
    volume_m3           REAL,
    declared_value      REAL,
    shipping_cost       REAL,
    payment_status      TEXT    NOT NULL DEFAULT 'unpaid'
                                CHECK(payment_status IN ('unpaid','paid','refunded')),
    status              TEXT    NOT NULL DEFAULT 'pending'
                                CHECK(status IN ('pending','collected','in_transit',
                                                 'out_for_delivery','delivered',
                                                 'delayed','returned','cancelled')),
    priority            TEXT    NOT NULL DEFAULT 'standard'
                                CHECK(priority IN ('standard','express','overnight')),
    notes               TEXT,
    created_by          TEXT,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Deliveries ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deliveries (
    delivery_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id         INTEGER NOT NULL REFERENCES shipments(shipment_id),
    driver_id           INTEGER REFERENCES drivers(driver_id),
    vehicle_id          INTEGER REFERENCES vehicles(vehicle_id),
    route_id            INTEGER REFERENCES routes(route_id),
    scheduled_date      TEXT,
    dispatched_at       TEXT,
    delivered_at        TEXT,
    delivery_status     TEXT    NOT NULL DEFAULT 'scheduled'
                                CHECK(delivery_status IN ('scheduled','dispatched',
                                                          'delivered','failed','returned')),
    recipient_name      TEXT,
    signature_obtained  INTEGER NOT NULL DEFAULT 0,
    proof_of_delivery   TEXT,
    notes               TEXT
);

-- ── Incidents ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS incidents (
    incident_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id     INTEGER REFERENCES shipments(shipment_id),
    delivery_id     INTEGER REFERENCES deliveries(delivery_id),
    incident_type   TEXT    NOT NULL CHECK(incident_type IN
                            ('delay','damage','failed_delivery','route_change','lost','other')),
    description     TEXT    NOT NULL,
    reported_by     TEXT,
    reported_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    resolved        INTEGER NOT NULL DEFAULT 0,
    resolved_at     TEXT,
    resolution_note TEXT
);

-- ── Indexes ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_shipments_tracking  ON shipments(tracking_number);
CREATE INDEX IF NOT EXISTS idx_shipments_status    ON shipments(status);
CREATE INDEX IF NOT EXISTS idx_deliveries_shipment ON deliveries(shipment_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_driver   ON deliveries(driver_id);
CREATE INDEX IF NOT EXISTS idx_inventory_warehouse ON inventory(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_inventory_sku       ON inventory(sku);
CREATE INDEX IF NOT EXISTS idx_audit_actor         ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_action        ON audit_log(action);
"""


# ---------------------------------------------------------------------------
# DatabaseManager
# ---------------------------------------------------------------------------

class DatabaseManager:
    """
    Single access point for all database operations.

    All public methods return plain dicts (or lists of dicts) so the rest
    of the application stays decoupled from SQLite internals.
    """

    def __init__(self, db_path: str = "logistics.db"):
        self._path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self._connect()
        self._apply_schema()
        logger.info("Database ready — %s", self._path)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row          # rows behave like dicts
        self._conn.execute("PRAGMA journal_mode=WAL")  # better concurrency
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")

    def _apply_schema(self) -> None:
        with self._conn:
            self._conn.executescript(SCHEMA_SQL)
        logger.info("Schema applied successfully.")

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Database connection closed.")

    @contextmanager
    def _tx(self):
        """Context manager for explicit transactions with rollback on error."""
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def _row_to_dict(self, row: sqlite3.Row | None) -> dict | None:
        return dict(row) if row else None

    def _rows_to_list(self, rows) -> list[dict]:
        return [dict(r) for r in rows]

    # ======================================================================
    # USERS
    # ======================================================================

    def create_user(self, username: str, password_hash: str, salt: str,
                    role: str, full_name: str, email: str = "",
                    phone: str = "", must_change_pwd: bool = False) -> int:
        sql = """
            INSERT INTO users
                (username, password_hash, salt, role, full_name,
                 email, phone, must_change_pwd)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._tx():
            cur = self._conn.execute(
                sql, (username, password_hash, salt, role,
                      full_name, email, phone, int(must_change_pwd))
            )
        logger.info("User created — username='%s' role='%s'", username, role)
        return cur.lastrowid

    def get_user_by_username(self, username: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM users WHERE username = ? AND is_active = 1",
            (username,)
        ).fetchone()
        return self._row_to_dict(row)

    def get_user_by_id(self, user_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return self._row_to_dict(row)

    def get_users_by_role(self, role: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM users WHERE role = ? AND is_active = 1", (role,)
        ).fetchall()
        return self._rows_to_list(rows)

    def get_all_users(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT user_id, username, role, full_name, email, phone, "
            "is_active, created_at FROM users ORDER BY username"
        ).fetchall()
        return self._rows_to_list(rows)

    def update_user(self, user_id: int, **fields) -> bool:
        allowed = {"full_name", "email", "phone", "role", "is_active", "must_change_pwd"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [user_id]
        with self._tx():
            self._conn.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
        logger.info("User %d updated — fields: %s", user_id, list(updates.keys()))
        return True

    def update_password(self, user_id: int, password_hash: str, salt: str) -> None:
        with self._tx():
            self._conn.execute(
                "UPDATE users SET password_hash=?, salt=?, must_change_pwd=0, "
                "updated_at=? WHERE user_id=?",
                (password_hash, salt, datetime.now().isoformat(), user_id)
            )
        logger.info("Password updated for user_id=%d", user_id)

    def deactivate_user(self, user_id: int) -> None:
        with self._tx():
            self._conn.execute(
                "UPDATE users SET is_active=0, updated_at=? WHERE user_id=?",
                (datetime.now().isoformat(), user_id)
            )
        logger.info("User %d deactivated.", user_id)

    # ======================================================================
    # AUDIT LOG
    # ======================================================================

    def write_audit_log(self, action: str, actor: str,
                        detail: str = "", timestamp: str = "") -> None:
        ts = timestamp or datetime.now().isoformat()
        with self._tx():
            self._conn.execute(
                "INSERT INTO audit_log (action, actor, detail, timestamp) VALUES (?,?,?,?)",
                (action, actor, detail, ts)
            )

    def get_audit_log(self, limit: int = 200, actor: str = "",
                      action: str = "") -> list[dict]:
        sql = "SELECT * FROM audit_log WHERE 1=1"
        params: list = []
        if actor:
            sql += " AND actor = ?"
            params.append(actor)
        if action:
            sql += " AND action = ?"
            params.append(action)
        sql += " ORDER BY log_id DESC LIMIT ?"
        params.append(limit)
        return self._rows_to_list(self._conn.execute(sql, params).fetchall())

    # ======================================================================
    # CUSTOMERS
    # ======================================================================

    def create_customer(self, name: str, email: str = "", phone: str = "",
                        address: str = "", city: str = "",
                        postcode: str = "", country: str = "UK") -> int:
        sql = """INSERT INTO customers (name, email, phone, address, city, postcode, country)
                 VALUES (?,?,?,?,?,?,?)"""
        with self._tx():
            cur = self._conn.execute(sql, (name, email, phone, address, city, postcode, country))
        logger.info("Customer created — name='%s'", name)
        return cur.lastrowid

    def get_customer_by_id(self, customer_id: int) -> dict | None:
        return self._row_to_dict(
            self._conn.execute("SELECT * FROM customers WHERE customer_id=?",
                               (customer_id,)).fetchone()
        )

    def search_customers(self, query: str) -> list[dict]:
        like = f"%{query}%"
        rows = self._conn.execute(
            "SELECT * FROM customers WHERE name LIKE ? OR email LIKE ? OR phone LIKE ?",
            (like, like, like)
        ).fetchall()
        return self._rows_to_list(rows)

    def get_all_customers(self) -> list[dict]:
        return self._rows_to_list(
            self._conn.execute("SELECT * FROM customers ORDER BY name").fetchall()
        )

    def update_customer(self, customer_id: int, **fields) -> None:
        allowed = {"name", "email", "phone", "address", "city", "postcode", "country"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [customer_id]
        with self._tx():
            self._conn.execute(
                f"UPDATE customers SET {set_clause} WHERE customer_id=?", values)

    # ======================================================================
    # WAREHOUSES
    # ======================================================================

    def create_warehouse(self, name: str, address: str, city: str,
                         postcode: str = "", capacity: float = 0.0,
                         manager_name: str = "", phone: str = "") -> int:
        sql = """INSERT INTO warehouses (name, address, city, postcode, capacity, manager_name, phone)
                 VALUES (?,?,?,?,?,?,?)"""
        with self._tx():
            cur = self._conn.execute(sql, (name, address, city, postcode,
                                           capacity, manager_name, phone))
        logger.info("Warehouse created — '%s'", name)
        return cur.lastrowid

    def get_all_warehouses(self) -> list[dict]:
        return self._rows_to_list(
            self._conn.execute(
                "SELECT * FROM warehouses WHERE is_active=1 ORDER BY name"
            ).fetchall()
        )

    def get_warehouse_by_id(self, warehouse_id: int) -> dict | None:
        return self._row_to_dict(
            self._conn.execute("SELECT * FROM warehouses WHERE warehouse_id=?",
                               (warehouse_id,)).fetchone()
        )

    def update_warehouse(self, warehouse_id: int, **fields) -> None:
        allowed = {"name", "address", "city", "postcode", "capacity",
                   "manager_name", "phone", "is_active"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [warehouse_id]
        with self._tx():
            self._conn.execute(
                f"UPDATE warehouses SET {set_clause} WHERE warehouse_id=?", values)

    # ======================================================================
    # INVENTORY
    # ======================================================================

    def add_inventory_item(self, warehouse_id: int, sku: str, name: str,
                           quantity: int = 0, reorder_level: int = 10,
                           description: str = "", category: str = "",
                           unit_weight_kg: float = 0.0,
                           location_code: str = "") -> int:
        sql = """INSERT INTO inventory
                    (warehouse_id, sku, name, description, category,
                     quantity, reorder_level, unit_weight_kg, location_code)
                 VALUES (?,?,?,?,?,?,?,?,?)"""
        with self._tx():
            cur = self._conn.execute(sql, (warehouse_id, sku, name, description,
                                           category, quantity, reorder_level,
                                           unit_weight_kg, location_code))
        logger.info("Inventory item added — SKU='%s' warehouse=%d", sku, warehouse_id)
        return cur.lastrowid

    def get_inventory_by_warehouse(self, warehouse_id: int) -> list[dict]:
        return self._rows_to_list(
            self._conn.execute(
                "SELECT * FROM inventory WHERE warehouse_id=? ORDER BY name",
                (warehouse_id,)
            ).fetchall()
        )

    def get_low_stock_items(self) -> list[dict]:
        """Return all items where quantity <= reorder_level."""
        return self._rows_to_list(
            self._conn.execute(
                "SELECT i.*, w.name AS warehouse_name FROM inventory i "
                "JOIN warehouses w ON i.warehouse_id = w.warehouse_id "
                "WHERE i.quantity <= i.reorder_level ORDER BY i.quantity"
            ).fetchall()
        )

    def update_stock(self, item_id: int, quantity_delta: int,
                     movement_type: str, reference: str = "",
                     performed_by: str = "", notes: str = "") -> None:
        """
        Adjust stock by *quantity_delta* (positive = add, negative = remove)
        and record the movement.
        """
        with self._tx():
            row = self._conn.execute(
                "SELECT quantity, warehouse_id FROM inventory WHERE item_id=?",
                (item_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Inventory item {item_id} not found.")
            new_qty = row["quantity"] + quantity_delta
            if new_qty < 0:
                raise ValueError("Stock cannot go below zero.")
            self._conn.execute(
                "UPDATE inventory SET quantity=?, updated_at=? WHERE item_id=?",
                (new_qty, datetime.now().isoformat(), item_id)
            )
            self._conn.execute(
                """INSERT INTO inventory_movements
                       (item_id, warehouse_id, movement_type, quantity,
                        reference, performed_by, notes)
                   VALUES (?,?,?,?,?,?,?)""",
                (item_id, row["warehouse_id"], movement_type,
                 abs(quantity_delta), reference, performed_by, notes)
            )

    def get_inventory_movements(self, item_id: int | None = None,
                                warehouse_id: int | None = None,
                                limit: int = 100) -> list[dict]:
        sql = "SELECT * FROM inventory_movements WHERE 1=1"
        params: list = []
        if item_id:
            sql += " AND item_id=?"
            params.append(item_id)
        if warehouse_id:
            sql += " AND warehouse_id=?"
            params.append(warehouse_id)
        sql += " ORDER BY movement_id DESC LIMIT ?"
        params.append(limit)
        return self._rows_to_list(self._conn.execute(sql, params).fetchall())

    # ======================================================================
    # VEHICLES
    # ======================================================================

    def add_vehicle(self, registration: str, make: str, model: str,
                    vehicle_type: str, capacity_kg: float,
                    year: int = 0, capacity_m3: float = 0.0,
                    notes: str = "") -> int:
        sql = """INSERT INTO vehicles
                    (registration, make, model, year, vehicle_type,
                     capacity_kg, capacity_m3, notes)
                 VALUES (?,?,?,?,?,?,?,?)"""
        with self._tx():
            cur = self._conn.execute(sql, (registration, make, model, year,
                                           vehicle_type, capacity_kg,
                                           capacity_m3, notes))
        logger.info("Vehicle added — reg='%s'", registration)
        return cur.lastrowid

    def get_all_vehicles(self) -> list[dict]:
        return self._rows_to_list(
            self._conn.execute(
                "SELECT * FROM vehicles ORDER BY registration"
            ).fetchall()
        )

    def get_available_vehicles(self) -> list[dict]:
        return self._rows_to_list(
            self._conn.execute(
                "SELECT * FROM vehicles WHERE status='available' ORDER BY capacity_kg"
            ).fetchall()
        )

    def get_vehicle_by_id(self, vehicle_id: int) -> dict | None:
        return self._row_to_dict(
            self._conn.execute("SELECT * FROM vehicles WHERE vehicle_id=?",
                               (vehicle_id,)).fetchone()
        )

    def update_vehicle_status(self, vehicle_id: int, status: str,
                              mileage_km: float | None = None) -> None:
        params: list = [status]
        sql = "UPDATE vehicles SET status=?"
        if mileage_km is not None:
            sql += ", mileage_km=?"
            params.append(mileage_km)
        sql += " WHERE vehicle_id=?"
        params.append(vehicle_id)
        with self._tx():
            self._conn.execute(sql, params)

    def update_vehicle_service(self, vehicle_id: int,
                               last_service: str, next_service: str) -> None:
        with self._tx():
            self._conn.execute(
                "UPDATE vehicles SET last_service_date=?, next_service_date=? "
                "WHERE vehicle_id=?",
                (last_service, next_service, vehicle_id)
            )

    # ======================================================================
    # DRIVERS
    # ======================================================================

    def add_driver(self, full_name: str, licence_number: str,
                   licence_expiry: str, licence_class: str = "",
                   phone: str = "", email: str = "",
                   shift_start: str = "", shift_end: str = "",
                   user_id: int | None = None) -> int:
        sql = """INSERT INTO drivers
                    (user_id, full_name, licence_number, licence_expiry,
                     licence_class, phone, email, shift_start, shift_end)
                 VALUES (?,?,?,?,?,?,?,?,?)"""
        with self._tx():
            cur = self._conn.execute(sql, (user_id, full_name, licence_number,
                                           licence_expiry, licence_class,
                                           phone, email, shift_start, shift_end))
        logger.info("Driver added — '%s'", full_name)
        return cur.lastrowid

    def get_all_drivers(self) -> list[dict]:
        return self._rows_to_list(
            self._conn.execute(
                "SELECT * FROM drivers ORDER BY full_name"
            ).fetchall()
        )

    def get_available_drivers(self) -> list[dict]:
        return self._rows_to_list(
            self._conn.execute(
                "SELECT * FROM drivers WHERE status='available' ORDER BY full_name"
            ).fetchall()
        )

    def get_driver_by_id(self, driver_id: int) -> dict | None:
        return self._row_to_dict(
            self._conn.execute("SELECT * FROM drivers WHERE driver_id=?",
                               (driver_id,)).fetchone()
        )

    def update_driver_status(self, driver_id: int, status: str) -> None:
        with self._tx():
            self._conn.execute(
                "UPDATE drivers SET status=? WHERE driver_id=?", (status, driver_id)
            )

    def update_driver(self, driver_id: int, **fields) -> None:
        allowed = {"full_name", "licence_expiry", "licence_class",
                   "phone", "email", "shift_start", "shift_end", "status"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [driver_id]
        with self._tx():
            self._conn.execute(
                f"UPDATE drivers SET {set_clause} WHERE driver_id=?", values)

    # ======================================================================
    # ROUTES
    # ======================================================================

    def add_route(self, name: str, origin: str, destination: str,
                  distance_km: float = 0.0, estimated_hours: float = 0.0,
                  notes: str = "") -> int:
        sql = """INSERT INTO routes (name, origin, destination, distance_km, estimated_hours, notes)
                 VALUES (?,?,?,?,?,?)"""
        with self._tx():
            cur = self._conn.execute(sql, (name, origin, destination,
                                           distance_km, estimated_hours, notes))
        return cur.lastrowid

    def get_all_routes(self) -> list[dict]:
        return self._rows_to_list(
            self._conn.execute("SELECT * FROM routes ORDER BY name").fetchall()
        )

    # ======================================================================
    # SHIPMENTS
    # ======================================================================

    def _generate_tracking_number(self) -> str:
        import random, string
        prefix = "LMS"
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=9))
        return f"{prefix}-{suffix}"

    def create_shipment(self, sender_id: int, receiver_id: int,
                        description: str = "",
                        weight_kg: float = 0.0, volume_m3: float = 0.0,
                        declared_value: float = 0.0,
                        shipping_cost: float = 0.0,
                        priority: str = "standard",
                        origin_warehouse: int | None = None,
                        dest_warehouse: int | None = None,
                        notes: str = "", created_by: str = "") -> tuple[int, str]:
        tracking = self._generate_tracking_number()
        sql = """INSERT INTO shipments
                    (tracking_number, sender_id, receiver_id,
                     origin_warehouse, dest_warehouse, description,
                     weight_kg, volume_m3, declared_value, shipping_cost,
                     priority, notes, created_by)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"""
        with self._tx():
            cur = self._conn.execute(sql, (
                tracking, sender_id, receiver_id,
                origin_warehouse, dest_warehouse, description,
                weight_kg, volume_m3, declared_value, shipping_cost,
                priority, notes, created_by
            ))
        shipment_id = cur.lastrowid
        logger.info("Shipment created — id=%d tracking='%s'", shipment_id, tracking)
        return shipment_id, tracking

    def get_shipment_by_id(self, shipment_id: int) -> dict | None:
        return self._row_to_dict(
            self._conn.execute("SELECT * FROM shipments WHERE shipment_id=?",
                               (shipment_id,)).fetchone()
        )

    def get_shipment_by_tracking(self, tracking_number: str) -> dict | None:
        return self._row_to_dict(
            self._conn.execute(
                "SELECT * FROM shipments WHERE tracking_number=?",
                (tracking_number,)
            ).fetchone()
        )

    def get_all_shipments(self, status: str = "", limit: int = 500) -> list[dict]:
        sql = """
            SELECT s.*,
                   c1.name AS sender_name,
                   c2.name AS receiver_name
            FROM shipments s
            LEFT JOIN customers c1 ON s.sender_id   = c1.customer_id
            LEFT JOIN customers c2 ON s.receiver_id  = c2.customer_id
            WHERE 1=1
        """
        params: list = []
        if status:
            sql += " AND s.status=?"
            params.append(status)
        sql += " ORDER BY s.shipment_id DESC LIMIT ?"
        params.append(limit)
        return self._rows_to_list(self._conn.execute(sql, params).fetchall())

    def update_shipment_status(self, shipment_id: int, status: str,
                               payment_status: str | None = None) -> None:
        fields: dict = {"status": status,
                        "updated_at": datetime.now().isoformat()}
        if payment_status:
            fields["payment_status"] = payment_status
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [shipment_id]
        with self._tx():
            self._conn.execute(
                f"UPDATE shipments SET {set_clause} WHERE shipment_id=?", values)

    def update_shipment(self, shipment_id: int, **fields) -> None:
        allowed = {"description", "weight_kg", "volume_m3", "declared_value",
                   "shipping_cost", "payment_status", "status", "priority",
                   "notes", "origin_warehouse", "dest_warehouse"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [shipment_id]
        with self._tx():
            self._conn.execute(
                f"UPDATE shipments SET {set_clause} WHERE shipment_id=?", values)

    # ======================================================================
    # DELIVERIES
    # ======================================================================

    def create_delivery(self, shipment_id: int,
                        driver_id: int | None = None,
                        vehicle_id: int | None = None,
                        route_id: int | None = None,
                        scheduled_date: str = "",
                        notes: str = "") -> int:
        sql = """INSERT INTO deliveries
                    (shipment_id, driver_id, vehicle_id, route_id,
                     scheduled_date, notes)
                 VALUES (?,?,?,?,?,?)"""
        with self._tx():
            cur = self._conn.execute(sql, (shipment_id, driver_id, vehicle_id,
                                           route_id, scheduled_date, notes))
            # Set shipment to in_transit
            self._conn.execute(
                "UPDATE shipments SET status='in_transit', updated_at=? "
                "WHERE shipment_id=?",
                (datetime.now().isoformat(), shipment_id)
            )
        delivery_id = cur.lastrowid
        logger.info("Delivery created — id=%d for shipment=%d", delivery_id, shipment_id)
        return delivery_id

    def get_delivery_by_id(self, delivery_id: int) -> dict | None:
        return self._row_to_dict(
            self._conn.execute("SELECT * FROM deliveries WHERE delivery_id=?",
                               (delivery_id,)).fetchone()
        )

    def get_deliveries_by_driver(self, driver_id: int) -> list[dict]:
        return self._rows_to_list(
            self._conn.execute(
                "SELECT d.*, s.tracking_number, s.description "
                "FROM deliveries d JOIN shipments s ON d.shipment_id=s.shipment_id "
                "WHERE d.driver_id=? ORDER BY d.scheduled_date",
                (driver_id,)
            ).fetchall()
        )

    def dispatch_delivery(self, delivery_id: int) -> None:
        now = datetime.now().isoformat()
        with self._tx():
            row = self._conn.execute(
                "SELECT shipment_id, vehicle_id, driver_id FROM deliveries "
                "WHERE delivery_id=?", (delivery_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Delivery {delivery_id} not found.")
            self._conn.execute(
                "UPDATE deliveries SET delivery_status='dispatched', dispatched_at=? "
                "WHERE delivery_id=?", (now, delivery_id)
            )
            self._conn.execute(
                "UPDATE shipments SET status='out_for_delivery', updated_at=? "
                "WHERE shipment_id=?", (now, row["shipment_id"])
            )
            if row["vehicle_id"]:
                self._conn.execute(
                    "UPDATE vehicles SET status='in_use' WHERE vehicle_id=?",
                    (row["vehicle_id"],)
                )
            if row["driver_id"]:
                self._conn.execute(
                    "UPDATE drivers SET status='on_route' WHERE driver_id=?",
                    (row["driver_id"],)
                )

    def complete_delivery(self, delivery_id: int, recipient_name: str = "",
                          signature_obtained: bool = False,
                          proof_of_delivery: str = "") -> None:
        now = datetime.now().isoformat()
        with self._tx():
            row = self._conn.execute(
                "SELECT shipment_id, vehicle_id, driver_id FROM deliveries "
                "WHERE delivery_id=?", (delivery_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Delivery {delivery_id} not found.")
            self._conn.execute(
                "UPDATE deliveries SET delivery_status='delivered', delivered_at=?, "
                "recipient_name=?, signature_obtained=?, proof_of_delivery=? "
                "WHERE delivery_id=?",
                (now, recipient_name, int(signature_obtained),
                 proof_of_delivery, delivery_id)
            )
            self._conn.execute(
                "UPDATE shipments SET status='delivered', updated_at=? "
                "WHERE shipment_id=?", (now, row["shipment_id"])
            )
            if row["vehicle_id"]:
                self._conn.execute(
                    "UPDATE vehicles SET status='available' WHERE vehicle_id=?",
                    (row["vehicle_id"],)
                )
            if row["driver_id"]:
                self._conn.execute(
                    "UPDATE drivers SET status='available' WHERE driver_id=?",
                    (row["driver_id"],)
                )
        logger.info("Delivery %d completed — shipment=%d", delivery_id, row["shipment_id"])

    def fail_delivery(self, delivery_id: int, reason: str = "") -> None:
        now = datetime.now().isoformat()
        with self._tx():
            row = self._conn.execute(
                "SELECT shipment_id, vehicle_id, driver_id FROM deliveries "
                "WHERE delivery_id=?", (delivery_id,)
            ).fetchone()
            self._conn.execute(
                "UPDATE deliveries SET delivery_status='failed', notes=? "
                "WHERE delivery_id=?", (reason, delivery_id)
            )
            self._conn.execute(
                "UPDATE shipments SET status='delayed', updated_at=? "
                "WHERE shipment_id=?", (now, row["shipment_id"])
            )
            if row["vehicle_id"]:
                self._conn.execute(
                    "UPDATE vehicles SET status='available' WHERE vehicle_id=?",
                    (row["vehicle_id"],)
                )
            if row["driver_id"]:
                self._conn.execute(
                    "UPDATE drivers SET status='available' WHERE driver_id=?",
                    (row["driver_id"],)
                )

    # ======================================================================
    # INCIDENTS
    # ======================================================================

    def log_incident(self, incident_type: str, description: str,
                     shipment_id: int | None = None,
                     delivery_id: int | None = None,
                     reported_by: str = "") -> int:
        sql = """INSERT INTO incidents
                    (shipment_id, delivery_id, incident_type,
                     description, reported_by)
                 VALUES (?,?,?,?,?)"""
        with self._tx():
            cur = self._conn.execute(sql, (shipment_id, delivery_id,
                                           incident_type, description,
                                           reported_by))
        logger.warning("Incident logged — type='%s' shipment=%s", incident_type, shipment_id)
        return cur.lastrowid

    def resolve_incident(self, incident_id: int, resolution_note: str = "") -> None:
        with self._tx():
            self._conn.execute(
                "UPDATE incidents SET resolved=1, resolved_at=?, resolution_note=? "
                "WHERE incident_id=?",
                (datetime.now().isoformat(), resolution_note, incident_id)
            )

    def get_open_incidents(self) -> list[dict]:
        return self._rows_to_list(
            self._conn.execute(
                "SELECT i.*, s.tracking_number FROM incidents i "
                "LEFT JOIN shipments s ON i.shipment_id=s.shipment_id "
                "WHERE i.resolved=0 ORDER BY i.reported_at DESC"
            ).fetchall()
        )

    def get_all_incidents(self, shipment_id: int | None = None) -> list[dict]:
        sql = "SELECT * FROM incidents WHERE 1=1"
        params: list = []
        if shipment_id:
            sql += " AND shipment_id=?"
            params.append(shipment_id)
        sql += " ORDER BY reported_at DESC"
        return self._rows_to_list(self._conn.execute(sql, params).fetchall())

    # ======================================================================
    # REPORTS
    # ======================================================================

    def report_delivery_progress(self) -> dict:
        """Summary counts of shipments grouped by status."""
        rows = self._conn.execute(
            "SELECT status, COUNT(*) AS total FROM shipments GROUP BY status"
        ).fetchall()
        return {r["status"]: r["total"] for r in rows}

    def report_warehouse_activity(self, warehouse_id: int | None = None,
                                  days: int = 30) -> list[dict]:
        """Inventory movements in the last *days* days, optionally for one warehouse."""
        since = f"datetime('now', '-{days} days')"
        sql = (
            f"SELECT m.*, i.name AS item_name, w.name AS warehouse_name "
            f"FROM inventory_movements m "
            f"JOIN inventory i ON m.item_id=i.item_id "
            f"JOIN warehouses w ON m.warehouse_id=w.warehouse_id "
            f"WHERE m.movement_date >= {since}"
        )
        params: list = []
        if warehouse_id:
            sql += " AND m.warehouse_id=?"
            params.append(warehouse_id)
        sql += " ORDER BY m.movement_date DESC"
        return self._rows_to_list(self._conn.execute(sql, params).fetchall())

    def report_vehicle_usage(self) -> list[dict]:
        """Delivery count and status for each vehicle."""
        return self._rows_to_list(
            self._conn.execute(
                "SELECT v.vehicle_id, v.registration, v.make, v.model, "
                "v.status, v.mileage_km, "
                "COUNT(d.delivery_id) AS total_deliveries "
                "FROM vehicles v "
                "LEFT JOIN deliveries d ON v.vehicle_id=d.vehicle_id "
                "GROUP BY v.vehicle_id ORDER BY total_deliveries DESC"
            ).fetchall()
        )

    def report_driver_activity(self) -> list[dict]:
        """Delivery count per driver."""
        return self._rows_to_list(
            self._conn.execute(
                "SELECT dr.driver_id, dr.full_name, dr.status, "
                "COUNT(d.delivery_id) AS total_deliveries "
                "FROM drivers dr "
                "LEFT JOIN deliveries d ON dr.driver_id=d.driver_id "
                "GROUP BY dr.driver_id ORDER BY total_deliveries DESC"
            ).fetchall()
        )

    def report_revenue(self, days: int = 30) -> dict:
        """Total revenue and paid/unpaid breakdown for recent shipments."""
        rows = self._conn.execute(
            f"SELECT payment_status, SUM(shipping_cost) AS total "
            f"FROM shipments "
            f"WHERE created_at >= datetime('now', '-{days} days') "
            f"GROUP BY payment_status"
        ).fetchall()
        return {r["payment_status"]: round(r["total"] or 0, 2) for r in rows}

    def report_incident_summary(self) -> list[dict]:
        """Count of incidents grouped by type."""
        return self._rows_to_list(
            self._conn.execute(
                "SELECT incident_type, "
                "COUNT(*) AS total, "
                "SUM(CASE WHEN resolved=1 THEN 1 ELSE 0 END) AS resolved, "
                "SUM(CASE WHEN resolved=0 THEN 1 ELSE 0 END) AS open "
                "FROM incidents GROUP BY incident_type"
            ).fetchall()
        )

    # ======================================================================
    # UTILITY
    # ======================================================================

    def execute_query(self, sql: str, params: tuple = ()) -> list[dict]:
        """
        Run a raw SELECT query (admin use only).
        Only SELECT statements are permitted.
        """
        if not sql.strip().upper().startswith("SELECT"):
            raise PermissionError("Only SELECT queries are allowed via execute_query.")
        return self._rows_to_list(self._conn.execute(sql, params).fetchall())

    def get_dashboard_stats(self) -> dict:
        """Aggregate numbers shown on the main dashboard."""
        def scalar(sql: str) -> int | float:
            row = self._conn.execute(sql).fetchone()
            return row[0] if row and row[0] is not None else 0

        return {
            "total_shipments":      scalar("SELECT COUNT(*) FROM shipments"),
            "active_deliveries":    scalar("SELECT COUNT(*) FROM deliveries "
                                          "WHERE delivery_status IN ('scheduled','dispatched')"),
            "delivered_today":      scalar("SELECT COUNT(*) FROM deliveries "
                                          "WHERE date(delivered_at)=date('now')"),
            "total_vehicles":       scalar("SELECT COUNT(*) FROM vehicles"),
            "available_vehicles":   scalar("SELECT COUNT(*) FROM vehicles WHERE status='available'"),
            "available_drivers":    scalar("SELECT COUNT(*) FROM drivers WHERE status='available'"),
            "low_stock_items":      scalar("SELECT COUNT(*) FROM inventory "
                                          "WHERE quantity <= reorder_level"),
            "open_incidents":       scalar("SELECT COUNT(*) FROM incidents WHERE resolved=0"),
            "revenue_this_month":   scalar("SELECT COALESCE(SUM(shipping_cost),0) FROM shipments "
                                          "WHERE payment_status='paid' "
                                          "AND strftime('%Y-%m',created_at)=strftime('%Y-%m','now')"),
        }