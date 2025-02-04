
from enum import Enum, IntEnum

class ProgressMetaType(Enum):
    FILE = pow(2, 0)
    LINE = pow(2, 1)
    INFO = pow(2, 2)
    LOG = pow(2, 3)
    RESULT = pow(2, 4)
    CHECK_POINTS = pow(2, 5)


class ProgressMetaTotal(IntEnum):
    File = 3
    Line = 3

class ProgressMetaFileStatus(Enum):
    Recived = 0
    Queued = 1
    Processed = 2
    Succeed = 3
    Failure = 3

class ProgressMetaLineStatus(Enum):
    Created = 0
    Queued = 1
    Processed = 2
    Succeed = 3
    Failure = 3

class LogLevel(Enum):
    TRACE = 1
    DEBUG = 2
    INFO = 3
    SUCCESS = 4
    WARNING = 5
    ERROR = 6
    CRITICAL = 7
