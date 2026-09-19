from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorDefinition:
    code: str
    name: str
    fatal: bool


ERRORS = {
    "E001": ErrorDefinition(
        "E001",
        "INVALID_VERSION",
        True,
    ),
    "E002": ErrorDefinition(
        "E002",
        "INVALID_COMMAND",
        True,
    ),
    "E003": ErrorDefinition(
        "E003",
        "INVALID_FORMAT",
        True,
    ),
    "E004": ErrorDefinition(
        "E004",
        "INVALID_LENGTH",
        True,
    ),
    "E005": ErrorDefinition(
        "E005",
        "INVALID_STATE",
        True,
    ),
    "E006": ErrorDefinition(
        "E006",
        "MESSAGE_TOO_LARGE",
        True,
    ),
    "E007": ErrorDefinition(
        "E007",
        "INVALID_MESSAGE_ID",
        True,
    ),
    "E008": ErrorDefinition(
        "E008",
        "INVALID_ACK",
        False,
    ),
    "E009": ErrorDefinition(
        "E009",
        "HANDSHAKE_TIMEOUT",
        True,
    ),
    "E010": ErrorDefinition(
        "E010",
        "ACK_TIMEOUT",
        False,
    ),
    "E011": ErrorDefinition(
        "E011",
        "PROTOCOL_ERROR",
        True,
    ),
    "E012": ErrorDefinition(
        "E012",
        "INVALID_PONG",
        False,
    ),
}


def get_error(code: str) -> ErrorDefinition:
    return ERRORS[code]
