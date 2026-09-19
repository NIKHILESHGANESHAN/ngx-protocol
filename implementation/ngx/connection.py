import socket
import time
from collections import deque

from .constants import (
    ACK_REQUESTED,
    ACK_TIMEOUT,
    MAX_ATTEMPTS,
    MAX_IN_FLIGHT_ACKED,
    ConnectionState,
    MessageType,
)
from .errors import ERRORS
from .frame import Frame
from .parser import FrameParser, ProtocolError
from .validation import validate_frame


class MessageIDGenerator:
    def __init__(self):
        self._next_id = 1

    def next(self):
        if self._next_id > 999999:
            raise RuntimeError("message ID limit reached")

        message_id = self._next_id
        self._next_id += 1
        return message_id


class PendingMessage:
    def __init__(self, frame):
        self.frame = frame
        self.attempts = 1
        self.last_sent = time.monotonic()


class NGXConnection:
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.parser = FrameParser()
        self.pending_frames = deque()

        self.ids = MessageIDGenerator()

        self.state = ConnectionState.HANDSHAKE

        self.pending_acks = {}
        self.processed_messages = set()

    def send_frame(
        self,
        message_type,
        payload=b"",
        flags=0,
    ):
        frame = Frame(
            message_type=message_type,
            flags=flags,
            message_id=self.ids.next(),
            payload=payload,
        )

        self.sock.sendall(frame.encode())

        return frame

    def send_error(self, code, detail=""):
        if code not in ERRORS:
            raise ValueError(
                f"Unknown NGX error code: {code}"
            )

        error = ERRORS[code]

        payload = (
            f"{error.code} {error.name}"
        )

        if detail:
            payload += f" {detail}"

        return self.send_frame(
            MessageType.ERROR.value,
            payload.encode("utf-8"),
            0,
        )

    def send_hello(self):
        return self.send_frame(
            MessageType.HELLO.value,
            b"",
            0,
        )

    def send_hello_ack(self):
        return self.send_frame(
            MessageType.HELLO_ACK.value,
            b"",
            0,
        )

    def send_msg(self, text, require_ack=False):
        if require_ack and (
            len(self.pending_acks)
            >= MAX_IN_FLIGHT_ACKED
        ):
            raise RuntimeError(
                "maximum number of in-flight "
                "ACK messages reached"
            )

        flags = (
            ACK_REQUESTED
            if require_ack
            else 0
        )

        frame = self.send_frame(
            MessageType.MSG.value,
            text.encode("utf-8"),
            flags,
        )

        if require_ack:
            self.pending_acks[
                frame.message_id
            ] = PendingMessage(frame)

        return frame

    def send_ack(self, message_id):
        return self.send_frame(
            MessageType.ACK.value,
            f"{message_id:06d}".encode("ascii"),
            0,
        )

    def send_ping(self):
        return self.send_frame(
            MessageType.PING.value,
            b"",
            0,
        )

    def send_pong(self, ping_id):
        return self.send_frame(
            MessageType.PONG.value,
            f"{ping_id:06d}".encode("ascii"),
            0,
        )

    def send_bye(self, reason=""):
        return self.send_frame(
            MessageType.BYE.value,
            reason.encode("utf-8"),
            0,
        )

    def receive_ack(self, frame):
        if frame.message_type != MessageType.ACK.value:
            return False

        if len(frame.payload) != 6:
            raise ProtocolError(
                "invalid ACK payload"
            )

        try:
            acknowledged_id = int(
                frame.payload.decode("ascii")
            )
        except (
            UnicodeDecodeError,
            ValueError,
        ) as exc:
            raise ProtocolError(
                "invalid ACK payload"
            ) from exc

        pending = self.pending_acks.pop(
            acknowledged_id,
            None,
        )

        if pending is not None:
            print(
                f"ACK received for "
                f"{acknowledged_id:06d}"
            )

        return True

    def check_retransmissions(self):
        now = time.monotonic()

        for (
            message_id,
            pending,
        ) in list(
            self.pending_acks.items()
        ):
            elapsed = (
                now - pending.last_sent
            )

            if elapsed < ACK_TIMEOUT:
                continue

            if (
                pending.attempts
                >= MAX_ATTEMPTS
            ):
                print(
                    f"ACK timeout: message "
                    f"{message_id:06d} failed "
                    f"after "
                    f"{pending.attempts} attempts"
                )

                del self.pending_acks[
                    message_id
                ]

                continue

            self.sock.sendall(
                pending.frame.encode()
            )

            pending.attempts += 1
            pending.last_sent = now

            print(
                f"Retransmitting message "
                f"{message_id:06d} "
                f"(attempt "
                f"{pending.attempts}/"
                f"{MAX_ATTEMPTS})"
            )

    def receive_message(self, frame):
        if (
            frame.message_type
            != MessageType.MSG.value
        ):
            return True

        if not (
            frame.flags & ACK_REQUESTED
        ):
            return True

        if (
            frame.message_id
            in self.processed_messages
        ):
            print(
                f"Duplicate MSG "
                f"{frame.message_id:06d} "
                f"ignored"
            )

            self.send_ack(
                frame.message_id
            )

            return False

        self.processed_messages.add(
            frame.message_id
        )

        self.send_ack(
            frame.message_id
        )

        return True

    def recv_frame(self):
        if self.pending_frames:
            return self.pending_frames.popleft()

        while True:
            self.check_retransmissions()

            data = self.sock.recv(4096)

            if not data:
                raise ConnectionError(
                    "peer closed the connection"
                )

            try:
                frames = self.parser.feed(
                    data
                )
            except ProtocolError:
                raise

            for frame in frames:
                try:
                    validate_frame(
                        frame,
                        self.state.value,
                    )
                except ValueError as exc:
                    error_text = str(exc)

                    code = error_text.split(
                        " ",
                        1,
                    )[0]

                    if code in ERRORS:
                        self.send_error(
                            code,
                            error_text,
                        )

                    if ERRORS.get(
                        code
                    ) and ERRORS[
                        code
                    ].fatal:
                        raise ProtocolError(
                            error_text
                        )

                    continue

                self.pending_frames.append(
                    frame
                )

            if self.pending_frames:
                return (
                    self.pending_frames.popleft()
                )

    def close(self):
        try:
            self.sock.shutdown(
                socket.SHUT_RDWR
            )
        except OSError:
            pass

        self.sock.close()
