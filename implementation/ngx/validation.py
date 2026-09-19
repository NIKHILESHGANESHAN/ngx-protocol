from .constants import (
    ACK_REQUESTED,
    MAX_PAYLOAD,
    MessageType,
)
from .errors import ERRORS


VALID_MESSAGE_TYPES = {
    message_type.value
    for message_type in MessageType
}


def validate_frame(frame, state):
    """
    Validate a parsed frame against NGX/0.1 rules.

    Raises:
        ValueError: protocol violation.
    """

    if frame.message_type not in VALID_MESSAGE_TYPES:
        raise ValueError(
            "E002 INVALID_COMMAND"
        )

    if not 0 <= frame.flags <= 0xFF:
        raise ValueError(
            "E003 INVALID_FORMAT"
        )

    # NGX/0.1 currently defines only bit 0.
    if frame.flags & ~ACK_REQUESTED:
        raise ValueError(
            "E003 INVALID_FORMAT"
        )

    if not 1 <= frame.message_id <= 999999:
        raise ValueError(
            "E007 INVALID_MESSAGE_ID"
        )

    if len(frame.payload) > MAX_PAYLOAD:
        raise ValueError(
            "E006 MESSAGE_TOO_LARGE"
        )

    # HELLO is only valid during handshake.
    if (
        frame.message_type == MessageType.HELLO.value
        and state != "HANDSHAKE"
    ):
        raise ValueError(
            "E005 INVALID_STATE"
        )

    # HELLO_ACK is only valid during handshake.
    if (
        frame.message_type == MessageType.HELLO_ACK.value
        and state != "HANDSHAKE"
    ):
        raise ValueError(
            "E005 INVALID_STATE"
        )

    # Application messages require an established session.
    if (
        frame.message_type
        in {
            MessageType.MSG.value,
            MessageType.ACK.value,
            MessageType.PING.value,
            MessageType.PONG.value,
        }
        and state != "ESTABLISHED"
    ):
        raise ValueError(
            "E005 INVALID_STATE"
        )

    return True
