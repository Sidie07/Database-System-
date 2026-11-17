"""
main.py — Logistics Management System Entry Point
Orchestrates startup: database initialisation, session management, and UI launch.
"""

import sys
import os
import logging
import hashlib
import secrets
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Logging configuration (set up before any imports that may log)
# ---------------------------------------------------------------------------

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "system.log"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger("main")


# ---------------------------------------------------------------------------
# Local module imports (database and ui modules expected alongside main.py)
# ---------------------------------------------------------------------------

try:
    from database import DatabaseManager
except ImportError as exc:
    logger.critical("Could not import 'database' module: %s", exc)
    sys.exit(1)

try:
    from ui import Application
except ImportError as exc:
    logger.critical("Could not import 'ui' module: %s", exc)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DB_PATH = "logistics.db"

# Role hierarchy — higher index = more permissions
ROLES = ["driver", "staff", "manager", "admin"]

# Default admin created on first run (password must be changed on first login)
DEFAULT_ADMIN = {
    "username": "admin",
    "password": "Admin@1234",   # plaintext — hashed before storage
    "role": "admin",
    "full_name": "System Administrator",
}


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Return (hashed_password, salt) using SHA-256 + random salt."""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return hashed, salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Return True if *password* matches the stored hash."""
    hashed, _ = _hash_password(password, salt)
    return secrets.compare_digest(hashed, stored_hash)


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

class Session:


    def __init__(self):
        self._user: dict | None = None
        self._token: str | None = None
        self._login_time: datetime | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def login(self, user_record: dict) -> str:
        """Store user info and return a session token."""
        self._user = user_record
        self._token = secrets.token_hex(32)
        self._login_time = datetime.now()
        logger.info(
            "Session opened — user='%s' role='%s'",
            user_record.get("username"),
            user_record.get("role"),
        )
        return self._token

    def logout(self) -> None:
        """Clear session state."""
        if self._user:
            logger.info("Session closed — user='%s'", self._user.get("username"))
        self._user = None
        self._token = None
        self._login_time = None

    def is_authenticated(self) -> bool:
        return self._user is not None and self._token is not None

    def has_role(self, minimum_role: str) -> bool:
        """Return True if the current user's role >= *minimum_role*."""
        if not self.is_authenticated():
            return False
        user_role = self._user.get("role", "driver")
        if user_role not in ROLES or minimum_role not in ROLES:
            return False
        return ROLES.index(user_role) >= ROLES.index(minimum_role)

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def user(self) -> dict | None:
        return self._user

    @property
    def username(self) -> str | None:
        return self._user.get("username") if self._user else None

    @property
    def role(self) -> str | None:
        return self._user.get("role") if self._user else None

    @property
    def login_time(self) -> datetime | None:
        return self._login_time


# ---------------------------------------------------------------------------
# Application controller
# ---------------------------------------------------------------------------

class LogisticsApp:
    """
    Top-level controller.

    Responsibilities
    ----------------
    * Initialise the database (schema + seed data).
    * Expose authenticate() for the UI login screen.
    * Hold the shared Session object passed to every UI view.
    * Start the Tkinter main loop.
    """

    def __init__(self):
        logger.info("=== Logistics Management System starting ===")
        self.db = DatabaseManager(DB_PATH)
        self.session = Session()
        self._ensure_default_admin()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _ensure_default_admin(self) -> None:
        """Create the default admin account if no admin exists."""
        try:
            admins = self.db.get_users_by_role("admin")
            if not admins:
                hashed, salt = _hash_password(DEFAULT_ADMIN["password"])
                self.db.create_user(
                    username=DEFAULT_ADMIN["username"],
                    password_hash=hashed,
                    salt=salt,
                    role=DEFAULT_ADMIN["role"],
                    full_name=DEFAULT_ADMIN["full_name"],
                )
                logger.warning(
                    "Default admin account created — please change the password on first login."
                )
            else:
                logger.info("Admin account(s) already exist — skipping seed.")
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to verify/create default admin: %s", exc)

    # ------------------------------------------------------------------
    # Authentication (called by the UI login screen)
    # ------------------------------------------------------------------

    def authenticate(self, username: str, password: str) -> bool:
        """
        Validate credentials, open a session, write an audit log entry.

        Returns True on success, False otherwise.
        """
        username = username.strip()
        if not username or not password:
            logger.warning("Login attempt with empty credentials.")
            return False

        try:
            user_record = self.db.get_user_by_username(username)
        except Exception as exc:
            logger.error("Database error during authentication: %s", exc)
            return False

        if user_record is None:
            logger.warning("Login failed — unknown user '%s'.", username)
            self._audit("LOGIN_FAIL", username, "Unknown user")
            return False

        stored_hash = user_record.get("password_hash", "")
        salt = user_record.get("salt", "")

        if not verify_password(password, stored_hash, salt):
            logger.warning("Login failed — wrong password for user '%s'.", username)
            self._audit("LOGIN_FAIL", username, "Wrong password")
            return False

        self.session.login(user_record)
        self._audit("LOGIN_SUCCESS", username, f"role={user_record.get('role')}")
        return True

    def logout(self) -> None:
        """Log the user out and write an audit entry."""
        if self.session.is_authenticated():
            self._audit("LOGOUT", self.session.username, "User logged out")
        self.session.logout()

    # ------------------------------------------------------------------
    # Audit logging
    # ------------------------------------------------------------------

    def _audit(self, action: str, actor: str, detail: str = "") -> None:
        """Persist an audit record to the database."""
        try:
            self.db.write_audit_log(
                action=action,
                actor=actor,
                detail=detail,
                timestamp=datetime.now().isoformat(),
            )
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to write audit log: %s", exc)

    # ------------------------------------------------------------------
    # Launch
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Instantiate and start the Tkinter UI."""
        try:
            app = Application(controller=self)
            app.mainloop()
        except Exception as exc:
            logger.critical("Unhandled exception in UI: %s", exc, exc_info=True)
            raise
        finally:
            self.db.close()
            logger.info("=== Logistics Management System stopped ===")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = LogisticsApp()
    app.run()


if __name__ == "__main__":
    main()