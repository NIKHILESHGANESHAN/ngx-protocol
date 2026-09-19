# NGX/0.1 Protocol Specification

**Status:** Draft / Reference Specification
**Protocol:** NGX/0.1
**Transport:** TCP
**Secure Deployment:** TLS 1.3

---

## 1. Overview

NGX/0.1 is a lightweight, stateful, message-oriented application protocol
designed to operate over a reliable TCP byte stream.

NGX provides:

- Connection establishment
- Application message exchange
- Application-level acknowledgement
- Retransmission of acknowledged messages
- Duplicate-message suppression
- Connection liveness using PING/PONG
- Graceful connection shutdown
- Structured protocol errors

NGX/0.1 does not replace TCP reliability. TCP provides reliable, ordered
byte-stream delivery. NGX adds application-level delivery acknowledgement
and duplicate suppression for messages that explicitly request acknowledgement.

The protocol is full-duplex. Each endpoint may independently send messages,
acknowledgements, PING/PONG frames, and shutdown frames according to the
connection state rules.

---

## 2. Transport

NGX/0.1 operates over TCP.

A connection consists of:

    Application
        |
      NGX/0.1
        |
      TCP
        |
       IP

The TCP connection provides:

- Ordered byte delivery
- Reliable byte delivery
- Connection-oriented transport

NGX MUST process the TCP stream as a sequence of NGX frames.

TCP packet boundaries MUST NOT be treated as NGX frame boundaries.

A single NGX frame MAY be split across multiple TCP reads.

Multiple NGX frames MAY be received in a single TCP read.

---

## 3. Secure Deployment

For secure deployments, NGX/0.1 MUST operate above TLS 1.3:

    Application
        |
      NGX/0.1
        |
      TLS 1.3
        |
       TCP
        |
        IP

TLS MUST be established before the NGX handshake begins.

NGX MUST NOT implement its own cryptographic protocol.

NGX/0.1 does not define STARTTLS.

The secure deployment profile uses normal TLS certificate validation.

Mutual TLS (mTLS) MAY be used when required by the deployment.

Plain TCP MAY be used for localhost development and protocol testing.

Credentials or passwords MUST NOT be transmitted in the NGX HELLO payload.

There is no protocol downgrade mechanism.

---

## 4. Connection Lifecycle

An NGX connection has three states:

    HANDSHAKE
        |
        v
    ESTABLISHED
        |
        v
      CLOSING

The following transitions are valid:

    HANDSHAKE -> ESTABLISHED
    ESTABLISHED -> CLOSING

No transition out of CLOSING is permitted.

A connection MUST begin in HANDSHAKE.

Application messages MUST NOT be exchanged until the connection reaches
ESTABLISHED.

---

## 5. Handshake

The TCP connection initiator MUST send HELLO first.

The TCP connection acceptor MUST wait for HELLO.

The handshake is:

    Initiator                         Acceptor
        |                                |
        | -------- HELLO --------------> |
        |                                |
        | <------- HELLO_ACK ------------|
        |                                |
        |       ESTABLISHED              |
        |                                |

HELLO and HELLO_ACK MUST contain:

- Flags = 00
- Empty payload
- Valid message ID

The protocol version is encoded in the frame prefix (`NGX/0.1`) and MUST NOT
be repeated in the HELLO payload.

The handshake MUST complete within HELLO_TIMEOUT.

Default:

    HELLO_TIMEOUT = 10 seconds

If the handshake timeout expires, the connection MUST fail with:

    E009 HANDSHAKE_TIMEOUT

---

## 6. Frame Format

Every NGX frame has an ASCII header followed by an optional binary payload.

The format is:

    NGX/0.1 TYPE FLAGS MESSAGE_ID PAYLOAD_LENGTH\r\n
    PAYLOAD

The header contains exactly five fields separated by a single ASCII space:

1. Protocol
2. Type
3. Flags
4. Message ID
5. Payload Length

Example:

    NGX/0.1 MSG 01 000001 5\r\nhello

The header terminator is exactly:

    \r\n

The payload consists of exactly PAYLOAD_LENGTH bytes.

PAYLOAD_LENGTH is measured in bytes, not characters.

A receiver MUST continue reading until the complete declared payload has
been received.

---

## 7. Message IDs

Every frame has a message ID.

Message IDs are decimal integers in the inclusive range:

    1 - 999999

Message IDs are encoded as six decimal digits in the wire representation.

Examples:

    000001
    000042
    123456

Message IDs are maintained independently in each direction.

Each endpoint therefore maintains its own outgoing message-ID sequence.

For normal application frames, message IDs MUST increase sequentially.

A receiver MUST reject:

- A message ID lower than the previous accepted ID
- A message ID that skips one or more IDs
- A message ID outside the valid range

Such violations use:

    E007 INVALID_MESSAGE_ID

---

## 8. Flags

The FLAGS field contains two hexadecimal digits.

Example:

    00
    01

Bit 0 is defined as:

    0x01 = ACK requested

All other flag bits are reserved.

Reserved flag bits MUST be zero in NGX/0.1.

A frame containing an unsupported/reserved flag MUST be rejected with:

    E003 INVALID_FORMAT

---

## 9. Payload Limit

The maximum NGX payload size is:

    MAX_PAYLOAD = 1,048,576 bytes
                = 1 MiB

A frame declaring a payload larger than this limit MUST be rejected with:

    E006 MESSAGE_TOO_LARGE

Implementations MUST NOT allocate unbounded memory based solely on an
attacker-controlled payload length.

---

## 10. Message Types

NGX/0.1 defines the following message types:

    HELLO
    HELLO_ACK
    MSG
    ACK
    PING
    PONG
    BYE
    ERROR

---

## 11. HELLO

HELLO starts the NGX handshake.

Requirements:

    State:         HANDSHAKE
    Flags:         00
    Payload:       empty
    ACK:           not requested

The initiator MUST send HELLO before any other normal NGX frame.

---

## 12. HELLO_ACK

HELLO_ACK confirms successful handshake processing.

Requirements:

    State:         HANDSHAKE
    Flags:         00
    Payload:       empty
    ACK:           not requested

After receiving a valid HELLO_ACK, the initiator MAY transition to
ESTABLISHED.

The acceptor MAY transition to ESTABLISHED after successfully sending
HELLO_ACK.

---

## 13. MSG

MSG carries application data.

MSG is valid only in:

    ESTABLISHED

MSG payloads in NGX/0.1 MUST be valid UTF-8 text.

MSG MAY request application-level acknowledgement.

Without acknowledgement:

    FLAGS = 00

With acknowledgement:

    FLAGS = 01

A MSG requesting acknowledgement MUST be tracked by the sender until it is
acknowledged or the maximum retransmission attempts are exhausted.

---

## 14. ACK

ACK confirms successful protocol-level receipt and acceptance of an
ACK-requested MSG.

An ACK MUST NOT itself request acknowledgement.

Requirements:

    Flags:         00
    Payload:       exactly six ASCII decimal digits

The payload contains the message ID being acknowledged.

Example:

    NGX/0.1 ACK 00 000010 6\r\n000009

An ACK means that the receiver:

1. Received the complete frame.
2. Successfully validated the frame.
3. Accepted the frame according to protocol rules.
4. Passed the message to the application.

ACK does NOT mean that:

- A human has read the message.
- The application has permanently stored the message.
- A later business operation succeeded.

---

## 15. ACK Reliability

NGX uses TCP for transport reliability and adds application-level
acknowledgement when requested by MSG.

Default acknowledgement timeout:

    ACK_TIMEOUT = 5 seconds

Maximum total transmissions:

    MAX_ATTEMPTS = 3

The initial transmission counts as attempt 1.

Therefore, an acknowledged message MAY be transmitted at most three times:

    Attempt 1
    Attempt 2
    Attempt 3

If no valid ACK is received after the final attempt, the message is considered
to have failed NGX-level acknowledgement.

ACK timeout is represented by:

    E010 ACK_TIMEOUT

E010 is a recoverable/application-level condition.

A late ACK received after retransmission MAY still complete the pending
message successfully.

A late ACK received after final failure MAY be ignored or logged.

---

## 16. Maximum Outstanding ACKs

An endpoint MUST NOT have more than:

    MAX_IN_FLIGHT_ACKED = 32

unacknowledged ACK-requested messages simultaneously.

This limit prevents unlimited growth of retransmission state.

---

## 17. Duplicate Message Suppression

NGX provides duplicate suppression for ACK-requested messages.

When a receiver has already processed an ACK-requested message ID during the
current TCP session, a retransmission of the same message ID MUST NOT cause
the application message to be processed again.

The receiver MUST send the ACK again for the duplicate message.

Example:

    Sender                         Receiver
       |                              |
       | -------- MSG 000010 ------> |
       |                              |
       | <--------- ACK 000010 ------ |
       |                              |
       |       ACK lost               |
       |                              |
       | -------- MSG 000010 ------> |
       |                              |
       |       duplicate              |
       | <--------- ACK 000010 ------ |
       |                              |

NGX therefore provides:

    At-least-once transmission with duplicate suppression.

NGX/0.1 does NOT provide a general exactly-once guarantee.

Applications performing state-changing operations SHOULD make those operations
idempotent.

---

## 18. PING

PING provides connection liveness.

PING is valid only in:

    ESTABLISHED

Requirements:

    Flags:         00
    Payload:       empty

PING does not request an ACK.

Each PING has a message ID.

The sender records the outstanding PING ID.

---

## 19. PONG

PONG is the response to PING.

PONG is valid only in:

    ESTABLISHED

Requirements:

    Flags:         00
    Payload:       exactly six ASCII decimal digits

The payload contains the message ID of the corresponding PING.

Example:

    PING:
    NGX/0.1 PING 00 000015 0\r\n

    PONG:
    NGX/0.1 PONG 00 000016 6\r\n000015

A PONG is valid only when its referenced PING ID is currently outstanding.

An unknown, duplicate, or otherwise invalid PONG MUST produce:

    E012 INVALID_PONG

E012 is non-fatal.

Structural PONG validation and semantic PONG correlation are separate:

- Frame validation checks the PONG structure.
- Connection logic checks whether the referenced PING is outstanding.

---

## 20. BYE

BYE performs graceful connection shutdown.

BYE MAY contain an optional UTF-8 reason.

BYE does not request acknowledgement.

BYE is valid in:

    ESTABLISHED
    CLOSING

An endpoint MAY send BYE once.

After sending BYE, the sender transitions to:

    CLOSING

A duplicate outgoing BYE is invalid:

    E005 INVALID_STATE

A peer receiving BYE SHOULD respond with its own BYE and then close the
underlying TCP connection.

A reciprocal BYE is permitted while the connection is already CLOSING.

An endpoint MUST NOT send application MSG, ACK, PING, or PONG frames after
entering CLOSING.

A TCP disconnect without a completed BYE exchange is considered an abnormal
shutdown.

---

## 21. ERROR

ERROR reports a protocol error.

The payload begins with:

    E### NAME

An optional human-readable detail MAY follow.

Example:

    E003 INVALID_FORMAT invalid header

ERROR frames do not request acknowledgement.

Defined errors are:

| Code | Name | Fatal |
|------|------|-------|
| E001 | INVALID_VERSION | Yes |
| E002 | INVALID_COMMAND | Yes |
| E003 | INVALID_FORMAT | Yes |
| E004 | INVALID_LENGTH | Yes |
| E005 | INVALID_STATE | Yes |
| E006 | MESSAGE_TOO_LARGE | Yes |
| E007 | INVALID_MESSAGE_ID | Yes |
| E008 | INVALID_ACK | No |
| E009 | HANDSHAKE_TIMEOUT | Yes |
| E010 | ACK_TIMEOUT | No |
| E011 | PROTOCOL_ERROR | Yes |
| E012 | INVALID_PONG | No |

For fatal protocol errors, the connection MUST NOT continue normal protocol
processing.

Recoverable errors MAY be handled without closing the connection, subject to
the specific semantics of the error.

---

## 22. Error Semantics

### E001 INVALID_VERSION

The protocol version in the frame does not match:

    NGX/0.1

This is fatal.

### E002 INVALID_COMMAND

The message type is not a defined NGX/0.1 command.

This is fatal.

### E003 INVALID_FORMAT

The frame structure or flags are malformed.

Examples include:

- Invalid header structure
- Non-ASCII header
- Invalid flag representation
- Reserved flag bits

This is fatal.

### E004 INVALID_LENGTH

A payload length field is invalid or structurally inconsistent.

This is fatal.

### E005 INVALID_STATE

A frame is not valid for the current connection state.

This is fatal.

### E006 MESSAGE_TOO_LARGE

The declared payload exceeds MAX_PAYLOAD.

This is fatal.

### E007 INVALID_MESSAGE_ID

A message ID is invalid or violates the expected sequence.

This is fatal.

### E008 INVALID_ACK

An ACK is malformed or references an invalid/unknown acknowledgement target.

This is recoverable.

### E009 HANDSHAKE_TIMEOUT

The HELLO handshake did not complete within the configured timeout.

This is fatal.

### E010 ACK_TIMEOUT

An ACK-requested message was not acknowledged within the retransmission
policy.

This is recoverable/application-level.

### E011 PROTOCOL_ERROR

Generic fatal protocol failure.

This is fatal.

### E012 INVALID_PONG

A PONG does not correspond to an outstanding PING.

This is non-fatal.

---

## 23. State Restrictions

The following command/state combinations are defined:

| Command | HANDSHAKE | ESTABLISHED | CLOSING |
|---------|-----------|-------------|---------|
| HELLO | Yes | No | No |
| HELLO_ACK | Yes | No | No |
| MSG | No | Yes | No |
| ACK | No | Yes | No |
| PING | No | Yes | No |
| PONG | No | Yes | No |
| BYE | No | Yes | Yes |
| ERROR | Error handling | Error handling | Error handling |

ERROR is intentionally not restricted to a single normal connection state
because an endpoint may need to report a protocol error while processing an
invalid frame, including during handshake.

---

## 24. Stream Processing

Receivers MUST process frames sequentially from the TCP byte stream.

The parser MUST support:

- Partial headers
- Partial payloads
- Multiple frames in one read
- Frame boundaries independent of TCP packet boundaries

A receiver MUST NOT assume that one TCP read contains exactly one NGX frame.

Malformed frames MUST NOT be silently ignored when they represent a fatal
protocol violation.

---

## 25. Validation Order

An implementation SHOULD validate frames in the following general order:

1. Parse the header.
2. Validate protocol version.
3. Validate message type.
4. Validate flags.
5. Validate message ID.
6. Validate payload length.
7. Read the complete payload.
8. Validate command-specific payload/state rules.
9. Apply message-ID sequencing rules.
10. Perform command-specific connection logic.

Implementations MUST ensure that malformed input cannot bypass state or
message-ID validation.

---

## 26. Full-Duplex Operation

Both endpoints may independently transmit NGX frames.

Message IDs are directional.

For example:

    Client -> Server
    IDs: 000001, 000002, 000003, ...

    Server -> Client
    IDs: 000001, 000002, 000003, ...

The two sequences are independent.

ACKs acknowledge messages received from the opposite direction.

---

## 27. Connection Shutdown Sequence

A normal client-initiated shutdown is:

    Client                          Server
      |                               |
      | -------- BYE --------------> |
      |                               |
      |        CLOSING                |
      |                               |
      | <------- BYE ---------------- |
      |                               |
      |       TCP close               |
      |                               |

A normal server-initiated shutdown follows the same principle with the
direction reversed.

After the reciprocal BYE exchange, the TCP connection SHOULD be closed.

---

## 28. Security Considerations

Implementations MUST enforce the maximum payload size.

Implementations MUST validate all numeric fields before using them.

Implementations MUST NOT trust message IDs supplied by peers.

Implementations MUST NOT assume that TCP packet boundaries represent NGX
frame boundaries.

Secure deployments SHOULD use TLS 1.3.

Applications requiring peer authentication SHOULD use normal TLS certificate
validation and MAY use mTLS.

NGX/0.1 does not define passwords, custom encryption, custom authentication,
or custom key exchange.

---

## 29. Resource Limits

The following default limits apply:

    MAX_PAYLOAD        = 1 MiB
    MAX_IN_FLIGHT_ACKED = 32
    ACK_TIMEOUT        = 5 seconds
    MAX_ATTEMPTS       = 3
    HELLO_TIMEOUT      = 10 seconds

Implementations MAY expose these as configuration parameters where compatible
with protocol interoperability.

Reducing a local limit MAY cause an implementation to reject traffic that
another implementation would otherwise accept.

---

## 30. Protocol Guarantees

NGX/0.1 provides:

- Ordered byte transport through TCP
- Application-level acknowledgement when requested
- Bounded retransmission
- Duplicate suppression for ACK-requested messages
- Full-duplex communication
- Connection liveness through PING/PONG
- Graceful shutdown through BYE
- Structured protocol errors

NGX/0.1 does not provide:

- Exactly-once application semantics
- Persistent message storage
- End-to-end durable delivery
- File transfer
- Streaming data channels
- Compression
- UDP transport
- Multicast
- Peer discovery
- Routing
- Multiplexed application channels
- Custom authentication
- Custom cryptography

---

## 31. Out of Scope for NGX/0.1

The following are intentionally excluded from version 0.1:

- File transfer
- Arbitrary binary DATA frames
- Compression
- UDP support
- Multicast
- Peer discovery
- Routing
- Multiplexed channels
- Custom authentication
- Custom cryptography
- Protocol downgrade
- STARTTLS
- Password authentication

Future protocol versions MAY define additional functionality while preserving
backward compatibility through an explicitly versioned protocol specification.

---

## 32. Reference Constants

The reference implementation defines:

    PROTOCOL = "NGX/0.1"

    MAX_PAYLOAD = 1_048_576

    MAX_IN_FLIGHT_ACKED = 32

    ACK_TIMEOUT = 5.0

    MAX_ATTEMPTS = 3

    HELLO_TIMEOUT = 10.0

    ACK_REQUESTED = 0x01

---

## 33. Versioning

This document specifies NGX/0.1.

The protocol version is carried in every NGX frame:

    NGX/0.1

An implementation MUST reject unsupported protocol versions.

Version incompatibility MUST be reported as:

    E001 INVALID_VERSION

No implicit downgrade is permitted.

---

## 34. Conformance

An NGX/0.1 implementation is conformant only if it:

1. Implements the NGX/0.1 frame format.
2. Enforces the defined payload limits.
3. Implements the defined connection states.
4. Enforces command/state restrictions.
5. Implements message-ID validation.
6. Implements ACK semantics.
7. Implements retransmission limits.
8. Implements duplicate suppression.
9. Implements PING/PONG semantics.
10. Implements BYE shutdown semantics.
11. Implements the defined protocol error model.

Implementations MAY provide additional local APIs or configuration options,
provided that their wire-level behavior remains compatible with this
specification.

---

## 35. Reference Session

A complete basic NGX/0.1 session may look like:

    Client                          Server
      |                               |
      | -------- HELLO ------------> |
      |                               |
      | <------- HELLO_ACK ---------- |
      |                               |
      | ===== ESTABLISHED =========== |
      |                               |
      | -------- MSG ---------------> |
      |                               |
      | <--------- ACK -------------- |
      |                               |
      | -------- PING --------------> |
      |                               |
      | <--------- PONG ------------- |
      |                               |
      | -------- BYE ---------------> |
      |                               |
      | ===== CLOSING =============== |
      |                               |
      | <--------- BYE -------------- |
      |                               |
      | -------- TCP CLOSE ----------|
      |                               |

---

## 36. End of Specification

NGX/0.1
