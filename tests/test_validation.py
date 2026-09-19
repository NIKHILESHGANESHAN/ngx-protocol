import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[1]
        / "implementation",
    ),
)

from ngx.connection import NGXConnection
from ngx.constants import ACK_REQUESTED, ConnectionState
from ngx.frame import Frame
from ngx.parser import ProtocolError
from ngx.validation import validate_frame


def test_unknown_command():
    frame = Frame(
        message_type="BANANA",
        flags=0,
        message_id=1,
        payload=b"",
    )

    with pytest.raises(
        ValueError,
        match="E002 INVALID_COMMAND",
    ):
        validate_frame(
            frame,
            "ESTABLISHED",
        )


def test_reserved_flag_rejected():
    frame = Frame(
        message_type="MSG",
        flags=0x02,
        message_id=1,
        payload=b"Hello",
    )

    with pytest.raises(
        ValueError,
        match="E003 INVALID_FORMAT",
    ):
        validate_frame(
            frame,
            "ESTABLISHED",
        )


def test_message_during_handshake_rejected():
    frame = Frame(
        message_type="MSG",
        flags=0,
        message_id=1,
        payload=b"Hello",
    )

    with pytest.raises(
        ValueError,
        match="E005 INVALID_STATE",
    ):
        validate_frame(
            frame,
            "HANDSHAKE",
        )


def test_invalid_message_id_rejected():
    frame = Frame(
        message_type="MSG",
        flags=0,
        message_id=0,
        payload=b"Hello",
    )

    with pytest.raises(
        ValueError,
        match="E007 INVALID_MESSAGE_ID",
    ):
        validate_frame(
            frame,
            "ESTABLISHED",
        )


def test_error_frame_is_sent():
    client_sock, server_sock = socket.socketpair()

    client = NGXConnection(client_sock)
    server = NGXConnection(server_sock)

    try:
        server.state = ConnectionState.ESTABLISHED

        invalid_frame = Frame(
            message_type="BANANA",
            flags=0,
            message_id=1,
            payload=b"",
        )

        client.sock.sendall(
            invalid_frame.encode()
        )

        with pytest.raises(
            ProtocolError,
            match="E002 INVALID_COMMAND",
        ):
            server.recv_frame()

        error = client.recv_frame()

        assert error.message_type == "ERROR"

        payload = error.payload.decode(
            "utf-8"
        )

        assert payload.startswith(
            "E002 INVALID_COMMAND"
        )

    finally:
        client.close()
        server.close()


def test_hello_payload_must_be_empty():
    frame = Frame(
        message_type="HELLO",
        flags=0,
        message_id=1,
        payload=b"Hello",
    )

    with pytest.raises(
        ValueError,
        match="E004 INVALID_LENGTH",
    ):
        validate_frame(
            frame,
            "HANDSHAKE",
        )


def test_ping_payload_must_be_empty():
    frame = Frame(
        message_type="PING",
        flags=0,
        message_id=1,
        payload=b"data",
    )

    with pytest.raises(
        ValueError,
        match="E004 INVALID_LENGTH",
    ):
        validate_frame(
            frame,
            "ESTABLISHED",
        )


def test_ack_cannot_request_ack():
    frame = Frame(
        message_type="ACK",
        flags=ACK_REQUESTED,
        message_id=1,
        payload=b"000001",
    )

    with pytest.raises(
        ValueError,
        match="E003 INVALID_FORMAT",
    ):
        validate_frame(
            frame,
            "ESTABLISHED",
        )


def test_invalid_ack_payload_rejected():
    frame = Frame(
        message_type="ACK",
        flags=0,
        message_id=1,
        payload=b"ABCDEF",
    )

    with pytest.raises(
        ValueError,
        match="E008 INVALID_ACK",
    ):
        validate_frame(
            frame,
            "ESTABLISHED",
        )


def test_ping_cannot_request_ack():
    frame = Frame(
        message_type="PING",
        flags=ACK_REQUESTED,
        message_id=1,
        payload=b"",
    )

    with pytest.raises(
        ValueError,
        match="E003 INVALID_FORMAT",
    ):
        validate_frame(
            frame,
            "ESTABLISHED",
        )


def test_pong_requires_six_digit_id():
    frame = Frame(
        message_type="PONG",
        flags=0,
        message_id=1,
        payload=b"123",
    )

    with pytest.raises(
        ValueError,
        match="E004 INVALID_LENGTH",
    ):
        validate_frame(
            frame,
            "ESTABLISHED",
        )


def test_handshake_timeout():
    client_sock, server_sock = socket.socketpair()

    client = NGXConnection(client_sock)
    server = NGXConnection(server_sock)

    try:
        # Pretend the 10-second timeout has already elapsed.
        server.handshake_started = (
            __import__("time").monotonic()
            - 11
        )

        with pytest.raises(
            ProtocolError,
            match="E009 HANDSHAKE_TIMEOUT",
        ):
            server.recv_frame()

        error = client.recv_frame()

        assert error.message_type == "ERROR"

        payload = error.payload.decode(
            "utf-8"
        )

        assert payload.startswith(
            "E009 HANDSHAKE_TIMEOUT"
        )

    finally:
        client.close()
        server.close()
