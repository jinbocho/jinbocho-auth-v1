from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


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
