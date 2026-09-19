from .constants import (
    ACK_REQUESTED,
    MAX_PAYLOAD,
    MessageType,
)


VALID_MESSAGE_TYPES = {
    message_type.value
    for message_type in MessageType
}


def validate_frame(frame, state):
    """
    Validate a parsed frame against NGX/0.1 rules.
    """

    # -------------------------
    # General frame validation
    # -------------------------

    if frame.message_type not in VALID_MESSAGE_TYPES:
        raise ValueError(
            "E002 INVALID_COMMAND"
        )

    if not 0 <= frame.flags <= 0xFF:
        raise ValueError(
            "E003 INVALID_FORMAT"
        )

    # Only bit 0 is currently defined.
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

    # -------------------------
    # Connection state rules
    # -------------------------

    if (
        frame.message_type == MessageType.HELLO.value
        and state != "HANDSHAKE"
    ):
        raise ValueError(
            "E005 INVALID_STATE"
        )

    if (
        frame.message_type == MessageType.HELLO_ACK.value
        and state != "HANDSHAKE"
    ):
        raise ValueError(
            "E005 INVALID_STATE"
        )

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

    if (
        frame.message_type == MessageType.BYE.value
        and state not in {"ESTABLISHED", "CLOSING"}
    ):
        raise ValueError(
            "E005 INVALID_STATE"
        )

    # -------------------------
    # Command-specific rules
    # -------------------------

    # HELLO
    if frame.message_type == MessageType.HELLO.value:
        if frame.flags != 0:
            raise ValueError(
                "E003 INVALID_FORMAT"
            )

        if len(frame.payload) != 0:
            raise ValueError(
                "E004 INVALID_LENGTH"
            )

    # HELLO_ACK
    elif frame.message_type == MessageType.HELLO_ACK.value:
        if frame.flags != 0:
            raise ValueError(
                "E003 INVALID_FORMAT"
            )

        if len(frame.payload) != 0:
            raise ValueError(
                "E004 INVALID_LENGTH"
            )

    # MSG
    elif frame.message_type == MessageType.MSG.value:
        try:
            frame.payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "E003 INVALID_FORMAT"
            ) from exc

    # ACK
    elif frame.message_type == MessageType.ACK.value:
        if frame.flags != 0:
            raise ValueError(
                "E003 INVALID_FORMAT"
            )

        if len(frame.payload) != 6:
            raise ValueError(
                "E008 INVALID_ACK"
            )

        try:
            text = frame.payload.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "E008 INVALID_ACK"
            ) from exc

        if not text.isdigit():
            raise ValueError(
                "E008 INVALID_ACK"
            )

        acknowledged_id = int(text)

        if not 1 <= acknowledged_id <= 999999:
            raise ValueError(
                "E008 INVALID_ACK"
            )

    # PING
    elif frame.message_type == MessageType.PING.value:
        if frame.flags != 0:
            raise ValueError(
                "E003 INVALID_FORMAT"
            )

        if len(frame.payload) != 0:
            raise ValueError(
                "E004 INVALID_LENGTH"
            )

    # PONG
    elif frame.message_type == MessageType.PONG.value:
        if frame.flags != 0:
            raise ValueError(
                "E003 INVALID_FORMAT"
            )

        if len(frame.payload) != 6:
            raise ValueError(
                "E004 INVALID_LENGTH"
            )

        try:
            text = frame.payload.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "E004 INVALID_LENGTH"
            ) from exc

        if not text.isdigit():
            raise ValueError(
                "E004 INVALID_LENGTH"
            )

        pong_id = int(text)

        if not 1 <= pong_id <= 999999:
            raise ValueError(
                "E007 INVALID_MESSAGE_ID"
            )

    # BYE
    elif frame.message_type == MessageType.BYE.value:
        if frame.flags != 0:
            raise ValueError(
                "E003 INVALID_FORMAT"
            )

        try:
            frame.payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "E003 INVALID_FORMAT"
            ) from exc

    # ERROR
    elif frame.message_type == MessageType.ERROR.value:
        if frame.flags != 0:
            raise ValueError(
                "E003 INVALID_FORMAT"
            )

        try:
            text = frame.payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "E003 INVALID_FORMAT"
            ) from exc

        if not text.startswith("E"):
            raise ValueError(
                "E003 INVALID_FORMAT"
            )

    return True
