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
