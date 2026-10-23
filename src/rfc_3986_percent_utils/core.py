"""RFC 3986 percent-encoding and decoding.

The standard library's ``urllib.parse.quote``/``unquote`` are close to what
RFC 3986 needs, but they bake in a couple of behaviours that are wrong for
strict URI work:

* ``quote`` defaults its ``safe`` argument to ``'/'``, which silently leaves
  path separators unencoded even when the caller asked for everything to be
  encoded.
* ``unquote`` replaces invalid UTF-8 sequences (``%C0%00``, lone continuation
  bytes) with U+FFFD and returns ``str`` — so you cannot tell whether the
  input was well-formed.

This module keeps the round-trip visible. Decoding to ``str`` raises on
malformed data; decoding to ``bytes`` never raises and is the safe path for
untrusted input.
"""

from __future__ import annotations

from typing import Iterable, Optional

__all__ = [
    "PercentCodec",
    "encode",
    "decode",
    "UNRESERVED",
    "SUB_DELIMS",
    "RESERVED",
]

# RFC 3986 section 2.2: reserved characters are split into gen-delims and
# sub-delims. They are reserved *because* they have structural meaning inside
# a URI; encoding them removes that meaning. We keep the sets separate so a
# caller can opt into exactly the level of reservation they need.
_GEN_DELIMS = frozenset(":/?#[]@")
SUB_DELIMS = frozenset("!$&'()*+,;=")
RESERVED = _GEN_DELIMS | SUB_DELIMS

# RFC 3986 section 2.3: unreserved characters may appear in a URI without
# percent-encoding and MUST NOT be encoded when produced by a normaliser.
# We default to leaving them alone so that ``encode('A_~')`` round-trips.
UNRESERVED = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
    "-._~"
)


class PercentCodec:
    """Configurable percent-encoder/decoder per RFC 3986.

    A codec is constructed once with a policy (which characters are safe) and
    applied many times. The policy is expressed as an explicit iterable so
    that callers can mix the named sets above with their own additions
    (e.g. a path component that must also keep ``%`` literal).

    ``safe`` is interpreted as: "characters in this set, AND any characters
    already expressed as valid ``%XX`` escapes, are left untouched."

    On decode, bytes outside the 7-bit ASCII range are rejected — RFC 3986
    defines percent-encoding over octets, and non-ASCII source bytes indicate
    a higher-level encoding step that this library does not perform.
    """

    def __init__(
        self,
        safe: Iterable[str] = (),
        *,
        plus_to_space: bool = False,
        decode_errors: str = "strict",
    ) -> None:
        self._safe = frozenset(safe)
        self._plus_to_space = plus_to_space
        self._decode_errors = decode_errors

    def encode(self, value: str) -> str:
        """Percent-encode ``value`` per the codec's safe set.

        Existing ``%XX`` sequences that are syntactically valid (percent sign
        followed by two hex digits) are preserved verbatim. This lets a caller
        encode a string that already contains escapes without double-encoding
        them.
        """
        if not value:
            return ""
        safe = self._safe
        out: list[str] = []
        i = 0
        n = len(value)
        while i < n:
            c = value[i]
            # Preserve existing, well-formed percent-escapes. We intentionally
            # do NOT preserve malformed ones (e.g. ``%GG``); those are encoded
            # like any other text.
            if c == "%" and i + 2 < n and _is_hex(value[i + 1]) and _is_hex(value[i + 2]):
                out.append(value[i : i + 3])
                i += 3
                continue
            if c in safe or c in UNRESERVED:
                out.append(c)
            else:
                # Encode as UTF-8 octets, then percent-escape each octet.
                for b in c.encode("utf-8"):
                    out.append("%%%02X" % b)
            i += 1
        return "".join(out)

    def decode(self, value: str) -> str:
        """Decode ``value``, raising on malformed data.

        Raises:
            ValueError: on a stray ``%``, a non-hex digit following ``%``,
                a truncated escape (``%4`` at end of string), or bytes that
                are not valid UTF-8.
            UnicodeDecodeError: propagated from the UTF-8 decode step when
                the assembled bytes are not a valid UTF-8 sequence.
        """
        return self._decode_str(value)

    def decode_bytes(self, value: str) -> bytes:
        """Decode ``value`` to raw bytes, never raising.

        Malformed escapes are copied literally (e.g. ``%GG`` stays as ``%GG``).
        This is the right call for untrusted input where you want the bytes
        for further inspection rather than a decoded string.
        """
        return self._decode_to_bytes(value, strict=False)

    # -- internals --------------------------------------------------------

    def _decode_str(self, value: str) -> str:
        # First collect raw octets, then UTF-8 decode. This lets us report a
        # single, consistent error for any malformed input.
        raw = self._decode_to_bytes(value, strict=True)
        return raw.decode("utf-8", errors=self._decode_errors)

    def _decode_to_bytes(self, value: str, strict: bool = True) -> bytes:
        out = bytearray()
        i = 0
        n = len(value)
        while i < n:
            c = value[i]
            if c == "%":
                if i + 2 >= n:
                    if strict:
                        raise ValueError(
                            "truncated percent-escape at position %d" % i
                        )
                    else:
                        out.extend(c.encode("utf-8"))
                        i += 1
                        continue
                h1 = value[i + 1]
                h2 = value[i + 2]
                if not (_is_hex(h1) and _is_hex(h2)):
                    if strict:
                        raise ValueError(
                            "invalid percent-escape '%%%s%s' at position %d"
                            % (h1, h2, i)
                        )
                    else:
                        out.extend(c.encode("utf-8"))
                        i += 1
                        continue
                out.append(int(h1 + h2, 16))
                i += 3
                continue
            if c == "+" and self._plus_to_space:
                out.append(0x20)
                i += 1
                continue
            if ord(c) > 0x7F:
                if strict:
                    raise ValueError(
                        "non-ASCII character %r at position %d; input must be 7-bit"
                        % (c, i)
                    )
                else:
                    out.extend(c.encode("utf-8"))
                    i += 1
                    continue
            out.extend(c.encode("utf-8"))
            i += 1
        return bytes(out)


_HEX = frozenset("0123456789abcdefABCDEF")


def _is_hex(c: str) -> bool:
    return c in _HEX


# --- module-level convenience wrappers ------------------------------------

_default_codec = PercentCodec(safe="")


def encode(value: str, safe: str = "") -> str:
    """Percent-encode ``value`` with ``safe`` characters preserved.

    Equivalent to ``PercentCodec(safe=...).encode(value)``.
    """
    return PercentCodec(safe=safe).encode(value)


def decode(value: str, *, plus_to_space: bool = False) -> str:
    """Decode ``value`` as percent-encoded text.

    Equivalent to ``PercentCodec(plus_to_space=...).decode(value)``.
    """
    return PercentCodec(plus_to_space=plus_to_space).decode(value)
