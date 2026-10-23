import unittest

from rfc_3986_percent_utils import (
    PercentCodec,
    SUB_DELIMS,
    UNRESERVED,
    decode,
    encode,
)


class TestEncode(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(encode(""), "")

    def test_unreserved_passthrough(self):
        for c in UNRESERVED:
            self.assertEqual(encode(c), c)

    def test_space_encoded_as_percent_20(self):
        self.assertEqual(encode(" "), "%20")

    def test_safe_characters_preserved(self):
        codec = PercentCodec(safe="/?#")
        self.assertEqual(codec.encode("a/b?c#d"), "a/b?c#d")

    def test_default_no_safe_leaves_slash_encoded(self):
        # Unlike urllib.parse.quote, we do not default safe to '/'.
        self.assertEqual(encode("a/b"), "a%2Fb")

    def test_existing_valid_escape_preserved(self):
        self.assertEqual(encode("a%20b"), "a%20b")

    def test_existing_malformed_escape_encoded(self):
        # %GG is not a valid escape, so the percent gets encoded.
        result = encode("%GG")
        self.assertEqual(result, "%25GG")

    def test_truncated_escape_encoded(self):
        result = encode("50%")
        self.assertEqual(result, "50%25")

    def test_non_ascii_utf8(self):
        self.assertEqual(encode("é"), "%C3%A9")
        self.assertEqual(encode("日本"), "%E6%97%A5%E6%9C%AC")

    def test_reserved_chars_encoded_by_default(self):
        for c in ":/?#[]@!$&'()*+,;=":
            self.assertEqual(encode(c), "%%%02X" % ord(c))


class TestDecode(unittest.TestCase):
    def test_round_trip_unreserved(self):
        s = "abc012-_~."
        self.assertEqual(decode(encode(s)), s)

    def test_round_trip_with_safe(self):
        codec = PercentCodec(safe="/?")
        s = "path/to?q r"
        self.assertEqual(codec.decode(codec.encode(s)), s)

    def test_decode_percent_20(self):
        self.assertEqual(decode("a%20b"), "a b")

    def test_decode_plus_no_special_handling(self):
        self.assertEqual(decode("a+b"), "a+b")

    def test_decode_plus_to_space(self):
        codec = PercentCodec(plus_to_space=True)
        self.assertEqual(codec.decode("a+b"), "a b")

    def test_decode_utf8_multibyte(self):
        self.assertEqual(decode("%C3%A9"), "é")
        self.assertEqual(decode("%E6%97%A5%E6%9C%AC"), "日本")

    def test_stray_percent_raises(self):
        with self.assertRaises(ValueError):
            decode("50%")

    def test_non_hex_after_percent_raises(self):
        with self.assertRaises(ValueError):
            decode("%GG")

    def test_truncated_escape_raises(self):
        with self.assertRaises(ValueError):
            decode("%4")

    def test_non_ascii_input_raises(self):
        with self.assertRaises(ValueError):
            decode("é")

    def test_invalid_utf8_bytes_raises(self):
        # 0xC3 0x29 is not a valid UTF-8 sequence.
        with self.assertRaises(UnicodeDecodeError):
            decode("%C3%29")


class TestDecodeBytes(unittest.TestCase):
    def test_valid_escape_returns_bytes(self):
        codec = PercentCodec()
        self.assertEqual(codec.decode_bytes("a%20b"), b"a b")

    def test_malformed_escape_copied_literally(self):
        codec = PercentCodec()
        self.assertEqual(codec.decode_bytes("%GG"), b"%GG")

    def test_truncated_escape_copied_literally(self):
        codec = PercentCodec()
        self.assertEqual(codec.decode_bytes("50%"), b"50%")

    def test_non_ascii_copied_literally(self):
        codec = PercentCodec()
        self.assertEqual(codec.decode_bytes("café"), b"caf\xc3\xa9")

    def test_plus_to_space(self):
        codec = PercentCodec(plus_to_space=True)
        self.assertEqual(codec.decode_bytes("a+b"), b"a b")

    def test_invalid_utf8_bytes_preserved(self):
        # No raise — raw bytes are returned.
        codec = PercentCodec()
        self.assertEqual(codec.decode_bytes("%C3%29"), b"\xc3)")


class TestSubDelimsConstant(unittest.TestCase):
    def test_sub_delims_membership(self):
        self.assertIn("$", SUB_DELIMS)
        self.assertNotIn("/", SUB_DELIMS)


if __name__ == "__main__":
    unittest.main()
