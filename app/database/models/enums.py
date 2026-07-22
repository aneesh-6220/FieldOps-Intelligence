"""Controlled Phase 1 lifecycle and classification values."""

from enum import StrEnum


class ValueEnum(StrEnum):
    """String enum with a readable presentation label."""

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()


class CustomerStatus(ValueEnum):
    PROSPECT = "prospect"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class LeadStatus(ValueEnum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    FOLLOW_UP = "follow_up"
    CONVERTED = "converted"
    LOST = "lost"


class LeadSource(ValueEnum):
    DOOR_TO_DOOR = "door_to_door"
    REFERRAL = "referral"
    WEBSITE = "website"
    SOCIAL_MEDIA = "social_media"
    REPEAT_CUSTOMER = "repeat_customer"
    PHONE = "phone"
    EMAIL = "email"
    OTHER = "other"


class Priority(ValueEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class PricingModel(ValueEnum):
    FIXED = "fixed"
    HOURLY = "hourly"
    PER_UNIT = "per_unit"
    CUSTOM = "custom"


class JobStatus(ValueEnum):
    UNSCHEDULED = "unscheduled"
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EmploymentStatus(ValueEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACTOR = "contractor"
    INACTIVE = "inactive"
