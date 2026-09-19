import socket

from .connection import NGXConnection
from .constants import ConnectionState, MessageType


HOST = "127.0.0.1"
PORT = 9000


def run_server():
    server_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    server_socket.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1,
    )

    server_socket.bind((HOST, PORT))
    server_socket.listen(1)

    print(
        f"NGX server listening on "
        f"{HOST}:{PORT}"
    )

    client_socket, address = server_socket.accept()

    print(f"Connection from {address}")

    connection = NGXConnection(
        client_socket
    )

    try:
        frame = connection.recv_frame()

        if frame.message_type != MessageType.HELLO.value:
            print("Expected HELLO")
            return

        print("Received HELLO")

        connection.send_hello_ack()

        connection.state = (
            ConnectionState.ESTABLISHED
        )

        print("Connection established")

        while True:
            frame = connection.recv_frame()

            print(
                f"Received: "
                f"{frame.message_type} "
                f"id={frame.message_id}"
            )

            if frame.message_type == MessageType.MSG.value:

                is_new = connection.receive_message(
                    frame
                )

                if is_new:
                    text = frame.payload.decode(
                        "utf-8"
                    )

                    print(
                        f"MSG: {text}"
                    )

            elif frame.message_type == MessageType.ACK.value:

                connection.receive_ack(frame)

            elif frame.message_type == MessageType.PING.value:

                connection.send_pong(
                    frame.message_id
                )

                print(
                    f"PONG sent for "
                    f"{frame.message_id:06d}"
                )

            elif frame.message_type == MessageType.BYE.value:

                print(
                    "Client requested shutdown"
                )

                connection.send_bye(
                    "Goodbye"
                )

                break

            else:
                print(
                    f"Unhandled message type: "
                    f"{frame.message_type}"
                )

    except ConnectionError:
        print(
            "Client disconnected"
        )

    finally:
        connection.close()
        server_socket.close()

        print(
            "Server stopped"
        )


if __name__ == "__main__":
    run_server()
