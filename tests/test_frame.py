import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "implementation"))

from ngx.frame import Frame
from ngx.parser import FrameParser


def test_encode_decode():
    original = Frame(
        message_type="MSG",
        flags=1,
        message_id=1,
        payload=b"Hello",
    )

    encoded = original.encode()

    parser = FrameParser()
    frames = parser.feed(encoded)

    assert len(frames) == 1

    received = frames[0]

    assert received.message_type == "MSG"
    assert received.flags == 1
    assert received.message_id == 1
    assert received.payload == b"Hello"


def test_fragmented_frame():
    frame = Frame(
        message_type="MSG",
        flags=0,
        message_id=1,
        payload=b"Hello",
    )

    encoded = frame.encode()

    parser = FrameParser()

    assert parser.feed(encoded[:10]) == []

    frames = parser.feed(encoded[10:])

    assert len(frames) == 1
    assert frames[0].payload == b"Hello"


def test_multiple_frames():
    f1 = Frame("PING", 0, 1, b"")
    f2 = Frame("MSG", 0, 2, b"Hello")

    parser = FrameParser()

    frames = parser.feed(f1.encode() + f2.encode())

    assert len(frames) == 2
    assert frames[0].message_type == "PING"
    assert frames[1].message_type == "MSG"
