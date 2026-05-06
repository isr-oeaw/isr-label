from enum import Enum

class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"

class UserType(Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"
