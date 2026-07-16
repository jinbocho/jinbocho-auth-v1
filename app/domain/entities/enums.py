from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    # Self-service account for a child in a kids_mode_enabled library — never
    # appears in any require_role(...) allowlist for ordinary endpoints, so it
    # default-denies everything except the dedicated kids-mode surface.
    CHILD = "child"


class MembershipStatus(str, Enum):
    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class Language(str, Enum):
    EN = "en"
    IT = "it"
    ES = "es"
    FR = "fr"


class ThemeName(str, Enum):
    PERGAMENA = "pergamena"
    AKABENI = "akabeni"
    SUMI = "sumi"


class ThemeMode(str, Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"
