import socket
import time
import sys
from pathlib import Path

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[1]
        / "implementation"
    ),
)

from ngx.connection import NGXConnection
from ngx.constants import ACK_REQUESTED, ACK_TIMEOUT


def test_ack_requested_message():
    client_sock, server_sock = socket.socketpair()

    client = NGXConnection(client_sock)
    server = NGXConnection(server_sock)

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
    client_sock, server_sock = socket.socketpair()

    client = NGXConnection(client_sock)
    server = NGXConnection(server_sock)

    try:
        message = client.send_msg(
            "Duplicate test",
            require_ack=True,
        )

        # First delivery
        first = server.recv_frame()

        assert first.message_id == message.message_id

        assert server.receive_message(first) is True

        ack1 = client.recv_frame()

        assert ack1.message_type == "ACK"
        assert ack1.payload == (
            f"{message.message_id:06d}".encode("ascii")
        )

        client.receive_ack(ack1)

        # Simulate retransmission by sending the SAME
        # frame again from the client side.
        client.sock.sendall(first.encode())

        duplicate = server.recv_frame()

        assert duplicate.message_id == (
            message.message_id
        )

        # Server must recognize it as a duplicate.
        assert server.receive_message(
            duplicate
        ) is False

        # Server should send the ACK again.
        ack2 = client.recv_frame()

        assert ack2.message_type == "ACK"
        assert ack2.payload == (
            f"{message.message_id:06d}".encode("ascii")
        )

    finally:
        client.close()
        server.close()


def test_message_retransmission():
    client_sock, server_sock = socket.socketpair()

    client = NGXConnection(client_sock)
    server = NGXConnection(server_sock)

    try:
        message = client.send_msg(
            "Retransmission test",
            require_ack=True,
        )

        first = server.recv_frame()

        assert first.message_id == message.message_id
        assert first.payload == (
            b"Retransmission test"
        )

        # Deliberately do NOT send an ACK.

        pending = client.pending_acks[
            message.message_id
        ]

        # Pretend the ACK timeout has already happened.
        pending.last_sent = (
            time.monotonic()
            - ACK_TIMEOUT
            - 0.1
        )

        client.check_retransmissions()

        # The client should retransmit the exact same frame.
        retransmitted = server.recv_frame()

        assert retransmitted.message_id == (
            message.message_id
        )

        assert retransmitted.payload == (
            b"Retransmission test"
        )

        assert retransmitted.message_id == (
            first.message_id
        )

        assert (
            client.pending_acks[
                message.message_id
            ].attempts
            == 2
        )

        # Server processes the retransmission.
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
