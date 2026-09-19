import pytest

from ngx.parser import FrameParser, ProtocolError




def test_invalid_protocol_version_has_error_code():
    parser = FrameParser()

    with pytest.raises(ProtocolError) as exc_info:
        parser.feed(
            b"BAD/0.1 MSG 00 000001 0\r\n"
        )

    assert exc_info.value.code == "E001"


def test_invalid_header_has_format_error_code():
    parser = FrameParser()

    with pytest.raises(ProtocolError) as exc_info:
        parser.feed(
            b"NGX/0.1 MSG 00 000001\r\n"
        )

    assert exc_info.value.code == "E003"


def test_invalid_message_id_has_error_code():
    parser = FrameParser()

    with pytest.raises(ProtocolError) as exc_info:
        parser.feed(
            b"NGX/0.1 MSG 00 abcdef 0\r\n"
        )

    assert exc_info.value.code == "E007"


def test_invalid_payload_length_has_error_code():
    parser = FrameParser()

    with pytest.raises(ProtocolError) as exc_info:
        parser.feed(
            b"NGX/0.1 MSG 00 000001 abc\r\n"
        )

    assert exc_info.value.code == "E004"


def test_payload_too_large_has_error_code():
    parser = FrameParser()

    with pytest.raises(ProtocolError) as exc_info:
        parser.feed(
            b"NGX/0.1 MSG 00 000001 1048577\r\n"
        )

    assert exc_info.value.code == "E006"


def test_message_id_must_be_exactly_six_digits():
    parser = FrameParser()

    invalid_ids = [
        b"1",
        b"00001",
        b"0000001",
        b"+00001",
    ]

    for message_id in invalid_ids:
        with pytest.raises(ProtocolError) as exc_info:
            parser.feed(
                b"NGX/0.1 MSG 00 "
                + message_id
                + b" 0\r\n"
            )

        assert exc_info.value.code == "E007"


def test_six_digit_message_id_is_accepted():
    parser = FrameParser()

    frames = parser.feed(
        b"NGX/0.1 MSG 00 000042 0\r\n"
    )

    assert len(frames) == 1
    assert frames[0].message_id == 42


def test_flags_must_be_exactly_two_hex_digits():
    parser = FrameParser()

    invalid_flags = [
        b"0",
        b"001",
        b"GG",
    ]

    for flags in invalid_flags:
        with pytest.raises(ProtocolError) as exc_info:
            parser.feed(
                b"NGX/0.1 MSG "
                + flags
                + b" 000001 0\r\n"
            )

        assert exc_info.value.code == "E003"


def test_two_digit_hex_flags_are_accepted():
    parser = FrameParser()

    frames = parser.feed(
        b"NGX/0.1 MSG 0A 000001 0\r\n"
    )

    assert len(frames) == 1
    assert frames[0].flags == 0x0A


def test_truncated_header_waits_for_more_data():
    parser = FrameParser()

    assert parser.feed(
        b"NGX/0.1 MSG 00 000001"
    ) == []


def test_header_without_payload_waits_for_more_data():
    parser = FrameParser()

    assert parser.feed(
        b"NGX/0.1 MSG 00 000001 5\r\n"
    ) == []


def test_partial_payload_waits_for_remaining_bytes():
    parser = FrameParser()

    assert parser.feed(
        b"NGX/0.1 MSG 00 000001 5\r\nHel"
    ) == []

    frames = parser.feed(b"lo")

    assert len(frames) == 1
    assert frames[0].payload == b"Hello"
