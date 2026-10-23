"""Incremental terminal UI §5.3 decoder, with injected monotonic seconds.

Names match keymaps.json: up/down/left/right, home/end/pgup/pgdn,
f1..f12, shift-up etc., escape, enter, backspace, tab, shift-tab,
ctrl-a..ctrl-z. Printable keys retain their case and UTF-8 spelling.
Mouse reports, pasted content and unknown escape sequences never type.
"""

ESCAPE_TIMEOUT_SECONDS = .2  # Terminal UI 5.3: fragmented native input.


class KeyDecoder:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.escape_at: float | None = None
        self.paste = False
        self.discard_csi = False
        self.control_string = False
        self.after_cr = False

    def feed(self, data: bytes, now: float) -> list[str]:
        self.buffer.extend(data)
        result: list[str] = []
        while self.buffer:
            if self.control_string:
                ends = [(self.buffer.find(b"\x07"), 1), (self.buffer.find(b"\x1b\\"), 2)]
                found = [(index, size) for index, size in ends if index >= 0]
                if not found:
                    del self.buffer[:-1]
                    break
                index, size = min(found)
                del self.buffer[:index + size]
                self.control_string = False
                continue
            if self.paste:
                end = self.buffer.find(b"\x1b[201~")
                if end < 0:
                    del self.buffer[:-5]
                    break
                del self.buffer[:end + 6]
                self.paste = False
                continue
            if self.discard_csi:
                end = next((i for i, byte in enumerate(self.buffer) if 0x40 <= byte <= 0x7e), None)
                if end is None:
                    self.buffer.clear()
                    break
                del self.buffer[:end + 1]
                self.discard_csi = False
                continue
            byte = self.buffer[0]
            if self.after_cr:
                self.after_cr = False
                if byte in (0, 10):
                    del self.buffer[0]
                    continue
            if byte == 27:
                if self.escape_at is None:
                    self.escape_at = now
                if len(self.buffer) == 1:
                    break
                if self.buffer[1] in (93, 80, 94, 95):
                    del self.buffer[:2]
                    self.control_string = True
                    self.escape_at = None
                    continue
                if self.buffer[1] == 91:
                    end = next((i for i in range(2, len(self.buffer)) if 0x40 <= self.buffer[i] <= 0x7e), None)
                    if end is None:
                        if len(self.buffer) > 128:
                            self.buffer.clear()
                            self.discard_csi = True
                        break
                    sequence = bytes(self.buffer[:end + 1])
                    if sequence == b"\x1b[M":
                        if len(self.buffer) < 6:
                            break
                        del self.buffer[:6]
                        self.escape_at = None
                        continue
                    del self.buffer[:end + 1]
                    self.escape_at = None
                    if sequence == b"\x1b[200~":
                        self.paste = True
                        continue
                    key = self._csi(sequence[2:].decode("ascii", errors="ignore"))
                    if key:
                        result.append(key)
                    continue
                if self.buffer[1] == 79:
                    if len(self.buffer) < 3:
                        break
                    key = {65: "up", 66: "down", 67: "right", 68: "left", 72: "home", 70: "end",
                           73: "pgup", 71: "pgdn", 80: "f1", 81: "f2", 82: "f3", 83: "f4"}.get(self.buffer[2])
                    del self.buffer[:3]
                    self.escape_at = None
                    if key:
                        result.append(key)
                    continue
                # An unrecognised Alt chord is a whole sequence, not text.
                if self.buffer[1] < 32:
                    # Esc followed by a control hotkey is two independent
                    # actions, even when both arrive in one network packet.
                    del self.buffer[0]
                    self.escape_at = None
                    result.append("escape")
                    continue
                del self.buffer[:2]
                self.escape_at = None
                continue
            self.escape_at = None
            if byte < 32 or byte == 127:
                del self.buffer[0]
                if byte in (10, 13):
                    result.append("enter")
                    self.after_cr = byte == 13
                elif byte in (8, 127):
                    result.append("backspace")
                elif byte == 9:
                    result.append("tab")
                elif 1 <= byte <= 26:
                    result.append(f"ctrl-{chr(96 + byte)}")
                continue
            size = 1 if byte < 128 else 2 if 0xc2 <= byte <= 0xdf else 3 if 0xe0 <= byte <= 0xef else 4 if 0xf0 <= byte <= 0xf4 else 1
            if len(self.buffer) < size:
                break
            try:
                text = bytes(self.buffer[:size]).decode("utf-8")
            except UnicodeError:
                del self.buffer[0]
                continue
            del self.buffer[:size]
            result.append(text)
        return result

    @staticmethod
    def _csi(sequence: str) -> str | None:
        direct = {"A": "up", "B": "down", "C": "right", "D": "left", "H": "home", "F": "end", "Z": "shift-tab"}
        if sequence in direct:
            return direct[sequence]
        if sequence.startswith("1;2") and sequence[-1:] in ("A", "B", "C", "D", "H", "F"):
            return "shift-" + direct[sequence[-1]]
        if sequence in ("5;2~", "6;2~", "1;2~", "4;2~"):
            return {"5;2~": "shift-pgup", "6;2~": "shift-pgdn", "1;2~": "shift-home", "4;2~": "shift-end"}[sequence]
        return {"1~": "home", "7~": "home", "4~": "end", "8~": "end", "5~": "pgup", "6~": "pgdn",
                "11~": "f1", "12~": "f2", "13~": "f3", "14~": "f4", "15~": "f5", "17~": "f6",
                "18~": "f7", "19~": "f8", "20~": "f9", "21~": "f10", "23~": "f11", "24~": "f12"}.get(sequence)

    def flush(self, now: float) -> list[str]:
        if self.buffer == b"\x1b" and self.escape_at is not None and now - self.escape_at >= ESCAPE_TIMEOUT_SECONDS:
            self.buffer.clear()
            self.escape_at = None
            return ["escape"]
        return []
