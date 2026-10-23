"""Terminal UI §5.3, including byte-split remote terminal sequences."""

import pytest

from blacksite.door.keys import KeyDecoder, ESCAPE_TIMEOUT_SECONDS


@pytest.mark.parametrize("sequence,key", [
    (b"\x1b[A", "up"), (b"\x1b[B", "down"), (b"\x1b[C", "right"), (b"\x1b[D", "left"),
    (b"\x1bOA", "up"), (b"\x1bOD", "left"), (b"\x1b[H", "home"), (b"\x1b[1~", "home"),
    (b"\x1bOH", "home"), (b"\x1bOF", "end"), (b"\x1b[4~", "end"), (b"\x1b[F", "end"),
    (b"\x1b[5~", "pgup"), (b"\x1b[6~", "pgdn"), (b"\x1bOI", "pgup"), (b"\x1bOG", "pgdn"),
    (b"\x1b[5;2~", "shift-pgup"), (b"\x1b[6;2~", "shift-pgdn"),
    (b"\x1b[1;2A", "shift-up"), (b"\x1b[1;2D", "shift-left"), (b"\x1b[Z", "shift-tab"),
    (b"\x1bOP", "f1"), (b"\x1bOQ", "f2"), (b"\x1bOR", "f3"), (b"\x1bOS", "f4"),
    (b"\x1b[15~", "f5"), (b"\x1b[17~", "f6"), (b"\x1b[18~", "f7"), (b"\x1b[19~", "f8"),
    (b"\x1b[20~", "f9"), (b"\x1b[21~", "f10"), (b"\x1b[23~", "f11"), (b"\x1b[24~", "f12"),
    (b"\x08", "backspace"), (b"\x7f", "backspace"), (b"\x09", "tab"),
    (b"\x0f", "ctrl-o"), (b"\x06", "ctrl-f"), (b"\x10", "ctrl-p"), (b"j", "j"),
])
def test_decoding_split_at_every_byte(sequence: bytes, key: str) -> None:
    decoder = KeyDecoder()
    result = []
    for byte in sequence:
        result.extend(decoder.feed(bytes([byte]), 0))
    assert result == [key]


@pytest.mark.parametrize("data", [b"\r", b"\n", b"\r\n", b"\r\x00"])
def test_enter_variants(data: bytes) -> None:
    decoder = KeyDecoder()
    assert sum((decoder.feed(bytes([byte]), 0) for byte in data), []) == ["enter"]


def test_lone_escape_timeout() -> None:
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b", 0) == []
    assert ESCAPE_TIMEOUT_SECONDS == .2
    assert decoder.flush(.199) == []
    assert decoder.flush(.2) == ["escape"]


@pytest.mark.parametrize('tail,key', [(b'[C', 'right'), (b'[B', 'down'), (b'OD', 'left')])
def test_ui_5_3_native_fragment_after_fifty_ms_never_types_chat_hotkey(tail, key):
    decoder = KeyDecoder()
    assert decoder.feed(b'\x1b', 0) == []
    assert decoder.flush(.075) == []
    assert decoder.feed(tail, .09) == [key]
    assert decoder.flush(.3) == []


def test_utf8_text() -> None:
    decoder = KeyDecoder()
    result = sum((decoder.feed(bytes([byte]), 0) for byte in "界é".encode()), [])
    assert result == ["界", "é"]


@pytest.mark.parametrize("data", [b"\x1b[M !!", b"\x1b[<0;10;20M", b"\x1b[<0;10;20m", b"\x1b[99;7~"])
def test_mouse_and_unknown_csi_discarded_whole(data: bytes) -> None:
    decoder = KeyDecoder()
    assert sum((decoder.feed(bytes([byte]), 0) for byte in data), []) == []
    assert decoder.feed(b"x", 0) == ["x"]


def test_bracketed_paste_discarded_and_bounded() -> None:
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[200~" + b"x" * 100_000 + b"\x1b[20", 0) == []
    assert len(decoder.buffer) <= 5
    assert decoder.feed(b"1~j", 1) == ["j"]


def test_control_string_not_typed_and_escape_control_hotkey_survives() -> None:
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b]52;clipboard", 0) == []
    assert decoder.feed(b"\x07j\x1b\x18y", .01) == ["j", "escape", "ctrl-x", "y"]
