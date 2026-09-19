from enum import Enum


PROTOCOL = "NGX/0.1"

MAX_PAYLOAD = 1_048_576
MAX_IN_FLIGHT_ACKED = 32

ACK_TIMEOUT = 5.0
MAX_ATTEMPTS = 3
HELLO_TIMEOUT = 10.0

ACK_REQUESTED = 0x01


class MessageType(str, Enum):
    HELLO = "HELLO"
    HELLO_ACK = "HELLO_ACK"
    MSG = "MSG"
    ACK = "ACK"
    PING = "PING"
    PONG = "PONG"
    BYE = "BYE"
    ERROR = "ERROR"


class ConnectionState(str, Enum):
    HANDSHAKE = "HANDSHAKE"
    ESTABLISHED = "ESTABLISHED"
    CLOSING = "CLOSING"
