from enum import Enum

class ConditionOperator(str, Enum):
    EQ          = "eq"
    NEQ         = "neq"
    GT          = "gt"
    GTE         = "gte"
    LT          = "lt"
    LTE         = "lte"
    IN          = "in"
    NOT_IN      = "not-in"
    STARTS_WITH = "starts-with"
    ENDS_WITH   = "ends-with"
    MATCH       = "match"
