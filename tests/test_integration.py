import socket
import threading

from ngx.client import run_client
from ngx.server import run_server


def test_real_tcp_client_server_session(capsys):
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    finally:
        probe.close()

    server_thread = threading.Thread(
        target=run_server,
        kwargs={"host": "127.0.0.1", "port": port},
        daemon=True,
    )

    server_thread.start()

    client_error = {}

    def run_client_safely():
        try:
            run_client(
                host="127.0.0.1",
                port=port,
            )
        except Exception as exc:
            client_error["error"] = exc

    client_thread = threading.Thread(
        target=run_client_safely,
        daemon=True,
    )

    client_thread.start()

    client_thread.join(timeout=2.0)

    assert not client_thread.is_alive(), (
        "NGX client integration test hung"
    )

    assert "error" not in client_error

    server_thread.join(timeout=2.0)

    assert not server_thread.is_alive(), (
        "NGX server integration test hung"
    )

    output = capsys.readouterr().out

    assert "HELLO_ACK received" in output
    assert "Connection established" in output
    assert "ACK received for" in output
    assert "PONG received for" in output
    assert "BYE received" in output


def test_real_tcp_server_rejects_invalid_protocol_version():
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    finally:
        probe.close()

    server_error = {}

    def run_server_safely():
        try:
            run_server(
                host="127.0.0.1",
                port=port,
            )
        except Exception as exc:
            server_error["error"] = exc

    server_thread = threading.Thread(
        target=run_server_safely,
        daemon=True,
    )

    server_thread.start()

    client = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )
    client.settimeout(1.0)

    try:
        client.connect(("127.0.0.1", port))

        client.sendall(
            b"BAD/0.1 MSG 00 000001 0\r\n"
        )

        header = b""

        while b"\r\n" not in header:
            chunk = client.recv(1024)
            assert chunk
            header += chunk

        header, payload = header.split(
            b"\r\n",
            1,
        )

        parts = header.decode("ascii").split(" ")

        assert parts[0] == "NGX/0.1"
        assert parts[1] == "ERROR"

        payload_length = int(parts[4])

        while len(payload) < payload_length:
            payload += client.recv(
                payload_length - len(payload)
            )

        payload = payload[:payload_length]

        assert payload.startswith(
            b"E001 INVALID_VERSION"
        )

    finally:
        client.close()

    server_thread.join(timeout=2.0)

    assert not server_thread.is_alive(), (
        "NGX server error integration test hung"
    )

    assert "error" in server_error
    assert "E001" in str(server_error["error"])
