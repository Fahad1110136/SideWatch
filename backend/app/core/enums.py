from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Implementation(str, Enum):
    VULNERABLE = "vulnerable"
    CONSTANT_TIME = "constant_time"


class SubmissionStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Decision(str, Enum):
    LEAK_DETECTED = "leak_detected"
    NO_LEAK_DETECTED = "no_leak_detected"
    INCONCLUSIVE = "inconclusive"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AuditOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"