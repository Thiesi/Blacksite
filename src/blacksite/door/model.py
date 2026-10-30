"""Pure display/input state. Game state and menu decisions stay on the server."""

from collections import deque
from copy import deepcopy
from typing import Any

from blacksite.hints import focus_context
from blacksite.door.cells import CellBuffer, truncate
from blacksite.door import chrome
from blacksite.door.doorinfo import DoorInfo
from blacksite.door.layout import compute
from blacksite.door.palette import Palette, resolve_tier
from blacksite.door.screens import SessionWarnings, first_run, help_pages, title
from blacksite.door.views import LinePrompt, Renderer, render_menu, render_text
from blacksite.door.views.zone import render_zone
from blacksite.door.views.lattice import render_lattice
from blacksite.door.log import rows as log_rows
from blacksite.door.present.context import Context
from blacksite.door.present.paint import Paint
from blacksite.door.present import screen as presentation_screen
from blacksite.server.protocol import Frame


class Display:
    def __init__(self, info: DoorInfo, request_prefix: str = "client", *, presentation: bool = False) -> None:
        self.info = info
        self.layout = compute(info.width, info.height)
        self.palette = Palette({}, resolve_tier(info.color_depth))
        self.presentation = presentation
        self.paint = Paint(self.palette)
        self.context = Context()
        self.body_safety: str | None = None
        self.kind = "text"
        self.body = title()
        self.revision = 0
        self.keymap: dict[str, Any] = {}
        self.local: dict[str, Any] | None = None
        self.local_lines: list[str | dict[str, str]] = []
        self.local_page = 0
        self.logs: deque[dict[str, Any]] = deque(maxlen=500)  # Game design §11.
        self.log_ids: set[str] = set()
        self.prompt: LinePrompt | None = None
        self.key_prompt: dict[str, Any] | None = None
        self.toast: tuple[str, str, float] | None = None
        self.confirm_exit = False
        self.leaving = False
        self.connected = False
        self.dirty = self.force_full = True
        self.last_render = -1.0
        self.previous: CellBuffer | None = None
        self.resync_pending = False
        self.hit_flash = False
        self.counter = 0
        self.request_prefix = request_prefix
        self.selected_keymap = "arrows"
        self.warnings = SessionWarnings(info.session_limit)
        self.renderers: dict[str, Renderer] = {"text": render_text, "dead": render_text, "menu": render_menu, "zone": render_zone, "lattice": render_lattice}

    def resize(self, info: DoorInfo) -> None:
        self.info = info
        self.layout = compute(info.width, info.height)
        self.previous = None
        self.force_full = self.dirty = True
        if self.local and self.local.get("title") == "SCROLLBACK":
            self.open_help(log_rows(list(self.logs), self.layout.text_area.width), "SCROLLBACK")

    def receive(self, frame: Frame, now: float) -> list[Frame]:
        old_hit = self.body.get("me",{}).get("hit_serial")
        data = frame.data
        result: list[Frame] = []
        if frame.type == "welcome":
            self.connected = True
            self.keymap = data.get("keymap", {})
            settings = data.get("player", {}).get("settings", {}) if isinstance(data.get("player"), dict) else {}
            self.selected_keymap = settings.get("keymap", "arrows")
            self.palette = Palette(data.get("palette", {}), resolve_tier(self.info.color_depth, settings.get("tier")), settings.get("palette", "default"))
            self.body, self.kind = title(data.get("motd", "")), "text"
            self.revision = 0
            if self.local is not None and self.local.get("title") == "HELP":
                self.local_lines = help_pages(self.keymap)
            self.resync_pending = False
            self.prompt = None
            self.key_prompt = None
            self.force_full = True
        elif frame.type == "view":
            self.revision, self.kind, self.body = data["rev"], data["kind"], deepcopy(data["body"])
            self.resync_pending = False
            self.force_full = True
            shown = self.body.get("body", {}) if self.kind == "wake" else self.body
            if shown.get("clear_prompt"):
                self.prompt = self.key_prompt = None
        elif frame.type == "delta":
            try:
                if self.resync_pending or data["base"] != self.revision or data["rev"] <= self.revision:
                    raise ValueError("delta base mismatch")
                document = {"kind": self.kind, "body": deepcopy(self.body)}
                self._patch(document, data["ops"])
                if not isinstance(document.get("body"), dict) or document.get("kind") not in ("zone", "lattice", "menu", "wake", "dead", "text"):
                    raise ValueError("invalid patched view")
                self.kind, self.body, self.revision = document["kind"], document["body"], data["rev"]
            except (ValueError, KeyError, IndexError, TypeError):
                if not self.resync_pending:
                    result.append(Frame("intent", {"name": "resync", "args": {}}))
                self.resync_pending = True
        elif frame.type == "log":
            for line in data["lines"]:
                token = line.get("id")
                if token and token in self.log_ids:
                    continue
                if len(self.logs) == self.logs.maxlen:
                    self.log_ids.discard(self.logs[0].get("id"))
                self.logs.append({**line, '_arrived': now} if self.presentation else line)
                if token:
                    self.log_ids.add(token)
        elif frame.type == "prompt":
            self.prompt = LinePrompt(data["id"], data["label"], min(200, data["max_len"])) if data["kind"] == "line" else None
            self.key_prompt = data if data["kind"] == "key" else None
        elif frame.type == "toast":
            self.toast = (data["text"], data["role"], now + data["seconds"])
        elif frame.type == "bye":
            self.connected = False
        elif frame.type == "pong":
            return []
        new_hit = self.body.get("me",{}).get("hit_serial")
        if old_hit is not None and new_hit is not None and new_hit != old_hit:
            self.hit_flash = True
        if self.presentation:
            shown = self.body.get('body', {}) if self.kind == 'wake' else self.body
            reported = shown.get('body_safety', shown.get('me', {}).get('safety'))
            if reported in ('safe', 'pocket', 'contested', 'open'):
                self.body_safety = reported
            elif self.kind == 'wake':
                self.body_safety = None  # A new Wake has no previous physical body.
        self.dirty = True
        return result

    @staticmethod
    def _patch(document: dict[str, Any], ops: list[dict[str, Any]]) -> None:
        if len(ops) > 256:
            raise ValueError("too many delta operations")
        for op in ops:
            path = op.get("path", "")
            if not isinstance(path, str) or not path.startswith("/") or len(path) > 1024:
                raise ValueError("invalid delta path")
            parts = [part.replace("~1", "/").replace("~0", "~") for part in path[1:].split("/")]
            if len(parts) > 16:
                raise ValueError("delta nesting limit")
            target: Any = document
            for part in parts[:-1]:
                if isinstance(target, list) and (not part.isdigit() or int(part) >= len(target)):
                    raise ValueError("invalid delta index")
                target = target[int(part)] if isinstance(target, list) else target[part]
            if isinstance(target, list) and parts[-1] != "-" and not parts[-1].isdigit():
                raise ValueError("invalid delta index")
            key: Any = int(parts[-1]) if isinstance(target, list) and parts[-1] != "-" else parts[-1]
            action = op.get("op")
            if action == "remove":
                del target[key]
            elif action in ("add", "replace"):
                value = deepcopy(op["value"])
                if isinstance(target, list) and action == "add":
                    if key == "-":
                        target.append(value)
                    elif isinstance(key, int) and 0 <= key <= len(target):
                        target.insert(key, value)
                    else:
                        raise ValueError("invalid delta index")
                else:
                    if action == "replace" and ((isinstance(target, dict) and key not in target) or (isinstance(target, list) and not 0 <= key < len(target))):
                        raise ValueError("missing replace target")
                    target[key] = value
            else:
                raise ValueError("unsupported delta operation")

    def open_help(self, lines: list[str | dict[str, str]] | None = None, heading: str = "HELP") -> None:
        self.local_lines = lines if lines is not None else help_pages(self.keymap)
        self.local_page = 0
        self.local = {"title": heading}
        self.dirty = True

    def refused(self, reason: str) -> None:
        self.connected = False
        self.local = self.prompt = self.key_prompt = None
        self.kind, self.body = "text", {"title": "DISCONNECTED", "lines": [
            "You are barred from the city." if reason == "banned" else "You cannot enter the city.",
            "Press any key to leave."], "page": 1, "pages": 1}
        self.dirty = self.force_full = True

    def key(self, key: str, now: float) -> list[Frame]:
        self.dirty = True
        if key == "ctrl-l":
            self.force_full = True
            return []
        if self.confirm_exit:
            self.confirm_exit = False
            if key.lower() == "y":
                self.leaving = True
                return [Frame("bye", {"reason": "logout"})] if self.connected else []
            return []
        if key == "ctrl-x":
            self.confirm_exit = True
            return []
        if self.prompt is not None:
            done, text = self.prompt.key(key)
            if done:
                prompt_id = self.prompt.id
                self.prompt = None
                if text is not None and self.connected:
                    return [Frame("line", {"id": prompt_id, "text": text})]
                if text is None and self.connected:
                    return [Frame("intent", {"name": "prompt_cancel", "args": {"id": prompt_id}})]
            return []
        if self.key_prompt is not None:
            self.key_prompt = None
            return [Frame("key", {"k": key, "t": max(0, int(now * 1000))})] if self.connected else []
        if self.local is not None:
            if key in ("escape", "b", "B"):
                self.local = None
            elif key in ("pagedown", "pageup", "pgdn", "pgup"):
                count = max(1, self.layout.text_area.height)
                pages = max(1, (len(self.local_lines) + count - 1) // count)
                self.local_page = max(0, min(pages - 1, self.local_page + (1 if key in ("pagedown", "pgdn") else -1)))
            return []
        if key == "?":
            self.open_help()
            return []  # S03 has no help subsystem; use the specified local fallback.
        if key == "ctrl-p" or (key == "L" and self.kind == "zone" and self.selected_keymap != "vi"):
            self.open_help(log_rows(list(self.logs), self.layout.text_area.width), "SCROLLBACK")
            return []
        if self.body.get("title") == "BLACKSITE" and key in ("i", "I"):
            self.open_help(first_run()["lines"], "WHAT THIS IS")
            return []
        if not self.connected:
            return []
        if self.kind == "text" and self.body.get("title") == "The tram hums." and key == "escape":
            self.open_help(log_rows(list(self.logs), self.layout.text_area.width), "SCROLLBACK")
            return []
        effective_kind = self.body.get("kind") if self.kind == "wake" else self.kind
        effective_body = self.body.get("body", {}) if self.kind == "wake" else self.body
        if effective_kind == "menu":
            if key == effective_body.get("jack_key"):
                return [Frame("intent", {"name": "lat.jack_out", "args": {}})]
            if key in ("escape", "b", "B"):
                return [Frame("intent", {"name": "menu_close", "args": {}})]
            if key in ("up", "down", "pageup", "pagedown", "pgup", "pgdn"):
                page = self.layout.menu.cursor_page
                distance = 1 if key in ("up", "down") else page
                return [Frame("intent", {"name": "menu_cursor", "args": {"delta": -distance if key in ("up", "pageup", "pgup") else distance}})]
            actions = {action.get("key") for action in effective_body.get("actions", [])}
            if key == "enter" or key in actions or key.lower() in actions:
                rows = effective_body.get("rows", [])
                cursor = effective_body.get("cursor", 0)
                selected = rows[cursor] if type(cursor) is int and 0 <= cursor < len(rows) else next((r for r in rows if r.get("id") == cursor), None)
                if (selected is not None or effective_body.get('kind') == 'talker'
                        and (key in actions or key.lower() in actions)):
                    self.counter += 1
                    return [Frame("intent", {"name": "menu_select", "args": {"row": selected["id"] if selected else '', "key": key.lower()},
                        "request_id": f"{self.request_prefix}-{self.counter}", "expected_revision": self.revision})]
            return []
        return [Frame("key", {"k": key, "t": max(0, int(now * 1000))})]

    def update(self, elapsed: float, now: float) -> None:
        if self.toast is not None and now >= self.toast[2]:
            self.toast = None
            self.dirty = True
        for text in self.warnings.update(elapsed):
            self.toast = (text, "warning", now + 8)
            self.dirty = True
        if elapsed >= self.info.session_limit:
            self.leaving = True

    def render(self, now: float) -> tuple[bytes, Frame | None]:
        if not self.dirty or now - self.last_render < 0.1:
            return b"", None
        buffer = CellBuffer(self.layout.width, self.layout.height, self.palette.style())
        hint = "? help  I what is this  Ctrl-X leave"
        if self.confirm_exit:
            hint = "Leave Karst? Y confirms; any other key returns."
        elif self.prompt:
            hint = f"{self.prompt.label}: {self.prompt.text}"
        elif self.key_prompt:
            hint = str(self.key_prompt["label"])
        elif "hint" in self.body:
            hint = str(self.body["hint"])
            if not self.presentation and self.kind == 'zone' and not self.body.get('me', {}).get('channel'):
                context = focus_context(self.body.get('focus'), self.body.get('jack_focus'),
                                        'Ctrl-O' if self.selected_keymap == 'vi' else 'J')
                hint = chrome.focus_hint(hint, self.layout.hint.width, context, self.body.get('objective'))
        if self.presentation:
            shown = self.body.get('body', {}) if self.kind == 'wake' else self.body
            primary = bool(self.confirm_exit or self.prompt or self.key_prompt
                           or shown.get('me', {}).get('channel'))
            zone_hint = self.kind == 'zone' and self.local is None and not primary
            context = focus_context(shown.get('focus'), shown.get('jack_focus'),
                                    'Ctrl-O' if self.selected_keymap == 'vi' else 'J') if zone_hint else []
            objective = shown.get('objective') if zone_hint else None
            hint = chrome.focus_hint(hint, self.layout.hint.width, context, objective,
                                     fit_all=True, primary=primary, objective_in_panel=self.layout.wide)
        header = "" if self.kind == "zone" and self.local is None else "Karst · " + truncate(self.info.handle, self.layout.header_slots.handle_width)
        if not self.presentation:
            chrome.render_frame(buffer, self.layout, self.palette, header, list(self.logs), hint)
        if self.local is not None:
            count = max(1, self.layout.text_area.height)
            body = {**self.local, "lines": self.local_lines[self.local_page * count:(self.local_page + 1) * count],
                    "page": self.local_page + 1, "pages": max(1, (len(self.local_lines) + count - 1) // count)}
            if self.presentation:
                self._present(buffer, 'text', body, hint, now)
            else:
                render_text(buffer, body, self.layout, self.palette)
        else:
            kind = self.body.get("kind") if self.kind == "wake" else self.kind
            body = self.body.get("body", {}) if self.kind == "wake" else self.body
            if self.presentation:
                if kind == 'zone':
                    self.context.choose(body, now)
                self._present(buffer, kind, body, hint, now)
            elif kind in self.renderers:
                chrome.render_view_shell(buffer, self.layout, self.palette, kind, body)
                self.renderers[kind](buffer, body, self.layout, self.palette)
        flashed = self.hit_flash
        if not self.presentation:
            chrome.render_effects(buffer, self.layout, self.palette, self.toast, flashed)
        if flashed:
            self.hit_flash = False
        output = buffer.diff(None if self.force_full else self.previous)
        output += chrome.cursor(self.layout, hint, bool(self.prompt and not self.confirm_exit))
        self.previous = buffer
        self.last_render = now
        self.force_full = False
        self.dirty = flashed
        return output, Frame("ack", {"rev": self.revision}) if self.connected else None

    def _present(self, buffer: CellBuffer, kind: str, body: dict[str, Any], hint: str, now: float) -> None:
        if self.paint.palette is not self.palette:
            self.paint = Paint(self.palette)
        presentation_screen.render(buffer, self.layout, self.paint, kind, body, list(self.logs), hint, now,
                                   flash=self.hit_flash, toast=self.toast, handle=self.info.handle,
                                   body_safety=self.body_safety)
