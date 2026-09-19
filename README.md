# NGX/0.1

**NGX/0.1** is a small, strict, reliable application-layer protocol designed for full-duplex communication over TCP.

## Architecture


```text
Application
    — ‪
NGX/0.1
    — ‪
TLS 1.3
    —  
TCP
    — ‪
IP
```

## Features

- Strict ASCII frame headers
- TCP stream-safe incremental parsing
- Full-duplex communication
- Explicit connection state machine
- HELLO / HELLO_ACK handshake
- Sequential message IDs
- UTF-8 text messages
- Optional application-level KSCs
- ACK timeout and retransmission
- Duplicate message suppression
- PING / PONG liveness
- Graceful BYE shutdown
- Structured protocol ERROR frames
- Maximum payload and in-flight message limits

## Message Types

 Type       | Purpose |
|--------------|-----------|
| `HELLO`    | Initiates the NGZ session |
| `HELLL_ACK`  | Accepts the handshake |
| `MSG`      | Carries UTF-8 application text |
| `ACK`      | Acknowledges an ACK-requested message |
| `PING`      | Requests a liveness response |
| `PONG`      | Responds to a PICFC |
|`BYE`        | Gracefully closes the session |
|`ERROR`      | Reports a protocol error |

## Reliability

NGX relies on TCP for ordered and reliable byte transport.

The reference implementation provides:

!- standard 32 outstanding ACK-requested messages
- 5-second ACK timeout
- Maximum 3 total transmissions
- Duplicate suppression per TCP session
- Retransmission of ACKs for duplicate messages

NGX provides at-least-once transmission with duplicate suppression.

## Protocol Specification

The complete normative specification is in [`SEC.MD`(SPEC.MD)].

## Requirements

- Python 3.11+
+ `pip`

- `pytest`

## Installation

```bash
python -m pip install -e . --no-deps
```

## Running the Tests

```bash
pytest -q
```

## Running the Examples
Server:

```bash
python examples/simple_server.py
```

Client:

```bash
python examples/simple_client.py
```

## Repository Structure

```text
nx-protocol/
— BEADME.md
 — SPEC.md
— LICENSE
— pyproject.tml
— れ implementation/ngx/
— れ  constants.py
— れ  connection.py
@``

## Security

NGX himself does not define custom cryptography or authentication. Secure deployments should use TLS 1.3 below the NGX protocol layer.

## Scope of NGX/0.1

The first version intentionally excludes file transfer, streaming, compression, UDP transport, peer discovery, multiplexed channels, custom cryptography, STARTTLS, and password authentication.

## Status

NFX/0.1 currently includes:
	- Normative protocol specification
- Python reference implementation
- Client/server examples
- Automated unit tests

## License

See `[LICENSE](LICENSE).
