from dataclasses import dataclass

from .constants import MAX_PAYLOAD, PROTOCOL


@dataclass(frozen=True)
class Frame:
    message_type: str
    flags: int
    message_id: int
    payload: bytes

    def encode(self) -> bytes:
        if not 0 <= self.flags <= 0xFF:
            raise ValueError("flags must be between 0 and 255")

        if not 1 <= self.message_id <= 999999:
            raise ValueError("message_id must be between 1 and 999999")

        if len(self.payload) > MAX_PAYLOAD:
            raise ValueError("payload exceeds maximum size")

        header = (
            f"{PROTOCOL} "
            f"{self.message_type} "
            f"{self.flags:02X} "
            f"{self.message_id:06d} "
            f"{len(self.payload)}\r\n"
        )

        return header.encode("ascii") + self.payload
