from .constants import MAX_PAYLOAD, PROTOCOL
from .frame import Frame


class ProtocolError(Exception):
    def __init__(self, message, code="E011"):
        super().__init__(message)
        self.code = code


class FrameParser:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[Frame]:
        self.buffer.extend(data)

        frames = []

        while True:
            frame = self._parse_one()

            if frame is None:
                break

            frames.append(frame)

        return frames

    def _parse_one(self):
        delimiter = self.buffer.find(b"\r\n")

        if delimiter == -1:
            return None

        header = bytes(self.buffer[:delimiter])

        try:
            header_text = header.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ProtocolError("header is not ASCII", "E003") from exc

        parts = header_text.split(" ")

        if len(parts) != 5:
            raise ProtocolError("invalid header", "E003")

        protocol, message_type, flags_text, id_text, length_text = parts

        if protocol != PROTOCOL:
            raise ProtocolError("invalid protocol version", "E001")

        try:
            flags = int(flags_text, 16)
        except ValueError as exc:
            raise ProtocolError("invalid flags", "E003") from exc

        try:
            message_id = int(id_text)
        except ValueError as exc:
            raise ProtocolError("invalid message ID", "E007") from exc

        try:
            payload_length = int(length_text)
        except ValueError as exc:
            raise ProtocolError("invalid payload length", "E004") from exc

        if not 1 <= message_id <= 999999:
            raise ProtocolError("invalid message ID", "E007")

        if not 0 <= payload_length <= MAX_PAYLOAD:
            raise ProtocolError("payload too large", "E006")

        payload_start = delimiter + 2
        payload_end = payload_start + payload_length

        if len(self.buffer) < payload_end:
            return None

        payload = bytes(self.buffer[payload_start:payload_end])

        del self.buffer[:payload_end]

        return Frame(
            message_type=message_type,
            flags=flags,
            message_id=message_id,
            payload=payload,
        )
