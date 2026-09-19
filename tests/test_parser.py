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
