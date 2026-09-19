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
from ngx.constants import (
    ACK_REQUESTED,
    ACK_TIMEOUT,
    ConnectionState,
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

        # Deliberately do not send an ACK.

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
        ) is True

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
