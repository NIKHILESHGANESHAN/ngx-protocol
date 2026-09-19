import pytest
import socket
import time
import sys
from pathlib import Path

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[1]
        / "implementation",
    ),
)

from ngx.connection import NGXConnection
from ngx.frame import Frame
from ngx.parser import ProtocolError
from ngx.constants import (
    ACK_REQUESTED,
    ACK_TIMEOUT,
    ConnectionState,
    MessageType,
)


def make_established_connections():
    client_sock, server_sock = socket.socketpair()

    client = NGXConnection(client_sock)
    server = NGXConnection(server_sock)

    client.state = ConnectionState.ESTABLISHED
    server.state = ConnectionState.ESTABLISHED

    return client, server


def test_ack_requested_message():
    client, server = make_established_connections()

    try:
        message = client.send_msg(
            "Reliability test",
            require_ack=True,
        )

        received = server.recv_frame()

        assert received.message_type == "MSG"
        assert received.message_id == message.message_id
        assert received.payload == b"Reliability test"
        assert received.flags & ACK_REQUESTED

        server.receive_message(received)

        ack = client.recv_frame()

        assert ack.message_type == "ACK"
        assert ack.payload == (
            f"{message.message_id:06d}".encode("ascii")
        )

        client.receive_ack(ack)

        assert message.message_id not in client.pending_acks

    finally:
        client.close()
        server.close()


def test_duplicate_message_is_not_processed_twice():
    client, server = make_established_connections()

    try:
        message = client.send_msg(
            "Duplicate test",
            require_ack=True,
        )

        first = server.recv_frame()

        assert first.message_id == message.message_id

        assert server.receive_message(first) is True

        ack1 = client.recv_frame()

        assert ack1.message_type == "ACK"
        assert ack1.payload == (
            f"{message.message_id:06d}".encode("ascii")
        )

        client.receive_ack(ack1)

        # Simulate retransmission of the SAME frame.
        client.sock.sendall(first.encode())

        duplicate = server.recv_frame()

        assert duplicate.message_id == message.message_id

        # The application must NOT process it twice.
        assert server.receive_message(duplicate) is False

        # The receiver sends the ACK again.
        ack2 = client.recv_frame()

        assert ack2.message_type == "ACK"
        assert ack2.payload == (
            f"{message.message_id:06d}".encode("ascii")
        )

    finally:
        client.close()
        server.close()


def test_message_retransmission():
    client, server = make_established_connections()

    try:
        message = client.send_msg(
            "Retransmission test",
            require_ack=True,
        )

        first = server.recv_frame()

        assert first.message_id == message.message_id
        assert first.payload == b"Retransmission test"

        # Simulate the receiver accepting the message,
        # but deliberately do not send/process the ACK.
        server.receive_message(first)

        # Deliberately do not let the sender receive the ACK.

        pending = client.pending_acks[
            message.message_id
        ]

        # Pretend the ACK timeout has already occurred.
        pending.last_sent = (
            time.monotonic()
            - ACK_TIMEOUT
            - 0.1
        )

        client.check_retransmissions()

        retransmitted = server.recv_frame()

        assert retransmitted.message_id == (
            message.message_id
        )

        assert retransmitted.payload == (
            b"Retransmission test"
        )

        # Same message ID = retransmission, not a new message.
        assert retransmitted.message_id == (
            first.message_id
        )

        assert (
            client.pending_acks[
                message.message_id
            ].attempts
            == 2
        )

        assert server.receive_message(
            retransmitted
        ) is False

        ack = client.recv_frame()

        assert ack.message_type == "ACK"
        assert ack.payload == (
            f"{message.message_id:06d}".encode("ascii")
        )

        client.receive_ack(ack)

        assert (
            message.message_id
            not in client.pending_acks
        )

    finally:
        client.close()
        server.close()


def test_message_id_gap_is_rejected():
    client, server = make_established_connections()

    try:
        first = client.send_msg("First")
        received = server.recv_frame()

        assert received.message_id == first.message_id

        # Skip message ID 000002 and send 000003 manually.
        from ngx.frame import Frame
        from ngx.constants import MessageType

        skipped = Frame(
            message_type=MessageType.MSG.value,
            flags=0,
            message_id=3,
            payload=b"Skipped ID",
        )

        client.sock.sendall(skipped.encode())

        with pytest.raises(ProtocolError, match="E007 INVALID_MESSAGE_ID"):
            server.recv_frame()
    finally:
        client.close()
        server.close()


def test_message_id_decrease_is_rejected():
    client, server = make_established_connections()

    try:
        first = client.send_msg("First")
        received = server.recv_frame()

        assert received.message_id == first.message_id

        from ngx.frame import Frame
        from ngx.constants import MessageType

        # Frame.encode() rejects ID 0, so construct ID 2 first,
        # then verify a backward ID using a valid frame.
        second = Frame(
            message_type=MessageType.MSG.value,
            flags=0,
            message_id=2,
            payload=b"Second",
        )
        client.sock.sendall(second.encode())

        received_second = server.recv_frame()
        assert received_second.message_id == 2

        backward = Frame(
            message_type=MessageType.MSG.value,
            flags=0,
            message_id=1,
            payload=b"Backward ID",
        )
        client.sock.sendall(backward.encode())

        with pytest.raises(ProtocolError, match="E007 INVALID_MESSAGE_ID"):
            server.recv_frame()
    finally:
        client.close()
        server.close()

def test_unknown_ack_is_rejected():
    client, server = make_established_connections()

    try:
        from ngx.frame import Frame
        from ngx.constants import MessageType

        ack = Frame(
            message_type=MessageType.ACK.value,
            flags=0,
            message_id=1,
            payload=b"999999",
        )

        with pytest.raises(
            ProtocolError,
            match="E008 INVALID_ACK",
        ):
            client.receive_ack(ack)

    finally:
        client.close()
        server.close()


def test_duplicate_ack_is_ignored():
    client, server = make_established_connections()

    try:
        message = client.send_msg(
            "ACK test",
            require_ack=True,
        )

        received = server.recv_frame()
        server.receive_message(received)

        ack = client.recv_frame()
        client.receive_ack(ack)

        assert message.message_id not in client.pending_acks

        # A second copy of the same ACK is harmless.
        client.receive_ack(ack)

        assert message.message_id not in client.pending_acks

    finally:
        client.close()
        server.close()


def test_malformed_ack_is_rejected():
    client, server = make_established_connections()

    try:
        from ngx.frame import Frame
        from ngx.constants import MessageType

        ack = Frame(
            message_type=MessageType.ACK.value,
            flags=0,
            message_id=1,
            payload=b"ABCDEF",
        )

        with pytest.raises(
            ProtocolError,
            match="E008 INVALID_ACK",
        ):
            client.receive_ack(ack)

    finally:
        client.close()
        server.close()


def test_recv_frame_automatically_retransmits_on_ack_timeout(
    monkeypatch,
):
    import threading

    monkeypatch.setattr(
        "ngx.connection.ACK_TIMEOUT",
        0.05,
    )

    client, server = make_established_connections()

    try:
        message = client.send_msg(
            "Automatic retransmission",
            require_ack=True,
        )

        first = server.recv_frame()

        assert first.message_id == message.message_id

        # Simulate successful application acceptance while
        # deliberately withholding the ACK.
        server.processed_messages.add(
            first.message_id
        )

        result = {}

        def wait_for_ack():
            try:
                result["frame"] = client.recv_frame()
            except Exception as exc:
                result["error"] = exc

        thread = threading.Thread(
            target=wait_for_ack,
            daemon=True,
        )
        thread.start()

        retransmitted = server.recv_frame()

        assert retransmitted.message_id == (
            message.message_id
        )

        assert retransmitted.payload == (
            b"Automatic retransmission"
        )

        assert (
            client.pending_acks[
                message.message_id
            ].attempts
            == 2
        )

        # Now acknowledge the retransmission.
        server.send_ack(message.message_id)

        thread.join(timeout=1.0)

        assert not thread.is_alive()
        assert "error" not in result

        ack = result["frame"]

        assert ack.message_type == "ACK"
        assert ack.payload == (
            f"{message.message_id:06d}".encode(
                "ascii"
            )
        )

        client.receive_ack(ack)

        assert (
            message.message_id
            not in client.pending_acks
        )

    finally:
        client.close()
        server.close()


def test_state_transition_handshake_to_established():
    client, server = make_established_connections()

    try:
        # Already established by the test helper.
        # Verify the transition API is idempotent.
        client.mark_established()

        assert (
            client.state
            == ConnectionState.ESTABLISHED
        )

    finally:
        client.close()
        server.close()


def test_state_transition_established_to_closing():
    client, server = make_established_connections()

    try:
        client.mark_closing()

        assert (
            client.state
            == ConnectionState.CLOSING
        )

    finally:
        client.close()
        server.close()


def test_invalid_state_transition_is_rejected():
    client, server = make_established_connections()

    try:
        client.mark_closing()

        with pytest.raises(
            ProtocolError,
            match="E005 INVALID_STATE",
        ):
            client.mark_established()

    finally:
        client.close()
        server.close()


def test_handshake_to_closing_is_rejected():
    client, server = make_established_connections()

    try:
        client.state = ConnectionState.HANDSHAKE

        with pytest.raises(
            ProtocolError,
            match="E005 INVALID_STATE",
        ):
            client.mark_closing()

    finally:
        client.close()
        server.close()


def test_invalid_message_id_sends_error_before_failure():
    client, server = make_established_connections()

    try:
        from ngx.frame import Frame
        from ngx.constants import MessageType

        client.sock.settimeout(1.0)

        invalid = Frame(
            message_type=MessageType.MSG.value,
            flags=0,
            message_id=2,
            payload=b"Invalid sequence",
        )

        client.sock.sendall(invalid.encode())

        with pytest.raises(
            ProtocolError,
            match="E007 INVALID_MESSAGE_ID",
        ):
            server.recv_frame()

        error = client.recv_frame()

        assert error.message_type == MessageType.ERROR.value
        assert error.payload.startswith(
            b"E007 INVALID_MESSAGE_ID"
        )

    finally:
        client.close()
        server.close()


def test_invalid_protocol_version_sends_error():
    client, server = make_established_connections()

    try:
        client.sock.settimeout(1.0)

        client.sock.sendall(
            b"BAD/0.1 MSG 00 000001 0\r\n"
        )

        with pytest.raises(
            ProtocolError,
            match="E001",
        ):
            server.recv_frame()

        error = client.recv_frame()

        assert error.message_type == MessageType.ERROR.value
        assert error.payload.startswith(
            b"E001 INVALID_VERSION"
        )

    finally:
        client.close()
        server.close()


def test_pong_for_outstanding_ping_is_accepted():
    client, server = make_established_connections()

    try:
        ping = client.send_ping()

        pong = Frame(
            message_type=MessageType.PONG.value,
            flags=0,
            message_id=1,
            payload=f"{ping.message_id:06d}".encode("ascii"),
        )

        assert client.receive_pong(pong) is True

    finally:
        client.close()
        server.close()


def test_unknown_pong_is_rejected():
    client, server = make_established_connections()

    try:
        pong = Frame(
            message_type=MessageType.PONG.value,
            flags=0,
            message_id=1,
            payload=b"000999",
        )

        with pytest.raises(
            ProtocolError,
            match="E012 INVALID_PONG",
        ):
            client.receive_pong(pong)

    finally:
        client.close()
        server.close()


def test_duplicate_pong_is_rejected():
    client, server = make_established_connections()

    try:
        ping = client.send_ping()

        pong = Frame(
            message_type=MessageType.PONG.value,
            flags=0,
            message_id=1,
            payload=f"{ping.message_id:06d}".encode("ascii"),
        )

        assert client.receive_pong(pong) is True

        with pytest.raises(
            ProtocolError,
            match="E012 INVALID_PONG",
        ):
            client.receive_pong(pong)

    finally:
        client.close()
        server.close()
