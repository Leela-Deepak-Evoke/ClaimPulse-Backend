from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    BILLER = "BILLER"


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class ClaimStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    PAID = "PAID"
    DENIED = "DENIED"
    RESUBMITTED = "RESUBMITTED"


class DenialReason(StrEnum):
    MISSING_INFORMATION = "Missing information"
    CODING_ERROR = "Coding error"
    EXPIRED_ELIGIBILITY = "Expired eligibility"
    DUPLICATE_CLAIM = "Duplicate claim"
    NOT_COVERED = "Not covered"
