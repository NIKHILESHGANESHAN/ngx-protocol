import socket

from .connection import NGXConnection
from .constants import MessageType


HOST = "127.0.0.1"
PORT = 9000


def run_client():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))

    connection = NGXConnection(sock)

    try:
        print(f"Connected to {HOST}:{PORT}")

        # 1. HELLO
        hello = connection.send_hello()
        print(f"HELLO sent, id={hello.message_id:06d}")

        # 2. HELLO_ACK
        frame = connection.recv_frame()

        if frame.message_type != MessageType.HELLO_ACK.value:
            raise RuntimeError("Expected HELLO_ACK")

        connection.mark_established()

        print("HELLO_ACK received")
        print("Connection established")

        # 3. MSG + ACK
        msg = connection.send_msg(
            "Hello from NGX client!",
            require_ack=True,
        )

        print(f"MSG sent, id={msg.message_id:06d}")

        while True:
            frame = connection.recv_frame()

            if frame.message_type == MessageType.ACK.value:
                connection.receive_ack(frame)

                acknowledged_id = int(
                    frame.payload.decode("ascii")
                )

                print(
                    f"ACK received for "
                    f"{acknowledged_id:06d}"
                )

                if acknowledged_id == msg.message_id:
                    break

        # 4. PING + PONG
        ping = connection.send_ping()

        print(f"PING sent, id={ping.message_id:06d}")

        while True:
            frame = connection.recv_frame()

            if frame.message_type == MessageType.PONG.value:
                connection.receive_pong(frame)

                pong_for = int(
                    frame.payload.decode("ascii")
                )

                print(
                    f"PONG received for "
                    f"{pong_for:06d}"
                )

                break

        # 5. BYE
        connection.send_bye("Client shutting down")
        connection.mark_closing()

        print("BYE sent")

        frame = connection.recv_frame()

        if frame.message_type == MessageType.BYE.value:
            print("BYE received")

    finally:
        connection.close()
        print("Client stopped")


if __name__ == "__main__":
    run_client()
