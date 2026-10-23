# rfc_3986_percent_utils

Percent-encodes and decodes URIs per RFC 3986 with configurable safe character sets.

```python
from rfc_3986_percent_utils import PercentCodec, encode, decode

# Module-level convenience: specify safe chars inline.
assert encode("a b/c", safe="/") == "a%20b/c"
assert decode("a%20b") == "a b"

# Or build a codec once and reuse it.
path_codec = PercentCodec(safe="/-._~")
assert path_codec.encode("a b/c") == "a%20b/c"
assert path_codec.decode("a%20b%2Fc") == "a b/c"
```

## Why this exists

`urllib.parse.quote` defaults its `safe` argument to `'/'`, which silently leaves path separators unencoded even when you asked for everything encoded. This library defaults `safe` to empty so that `encode("a/b")` produces `a%2Fb`, and you opt *into* keeping specific characters.

`unquote` replaces invalid UTF-8 sequences with U+FFFD and returns `str`, so you cannot tell whether the input was well-formed. `PercentCodec.decode` raises `ValueError` on a stray `%`, a non-hex digit after `%`, or a truncated escape; it raises `UnicodeDecodeError` when the assembled octets are not valid UTF-8. For untrusted input where you want the raw bytes without exceptions, use `decode_bytes`, which copies malformed escapes literally.

## Exports

- `encode(value: str, safe: str = "") -> str` — module-level convenience encoder.
- `decode(value: str, *, plus_to_space: bool = False) -> str` — module-level convenience decoder.
- `PercentCodec` — configurable codec with `encode`, `decode`, and `decode_bytes` methods.
- `UNRESERVED`, `SUB_DELIMS`, `RESERVED` — the RFC 3986 character sets, as `frozenset`.

## Interpretation decisions

- Input to `encode` is Python `str`; non-ASCII characters are encoded as their UTF-8 octets per RFC 3986 section 2.5. The library does not perform higher-level encoding (IDN, Punycode, etc.).
- `decode` accepts only 7-bit ASCII input (plus already-valid `%XX` escapes). Non-ASCII source characters raise `ValueError` because RFC 3986 percent-encoding is defined over octets, and a non-ASCII character indicates a higher-level encoding step that this library does not perform.
- Existing valid `%XX` sequences in the input to `encode` are preserved verbatim (no double-encoding). Malformed sequences like `%GG` or a trailing `%` are encoded like any other text.
- `plus_to_space` defaults to `False`. RFC 3986 does not define `+` as space; that is an `application/x-www-form-urlencoded` convention. The flag exists for callers that need both.

## Awkward edge

`PercentCodec.decode("%C3%29")` raises `UnicodeDecodeError` because `0xC3 0x29` is not a valid UTF-8 sequence. If you would rather get the raw bytes and inspect them yourself, call `decode_bytes`, which never raises and returns the raw `bytes`.
