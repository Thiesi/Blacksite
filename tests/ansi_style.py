"""Independent semantic SGR state for presentation verification."""

from dataclasses import dataclass, replace

Colour = tuple[int, ...]  # (mode, value...), mode 0=ANSI, 1=indexed, 2=RGB.


@dataclass(frozen=True)
class Rendition:
    foreground: Colour = (0, 7)
    background: Colour = (0, 0)
    attributes: tuple[int, ...] = ()

    def apply(self, arguments: str) -> "Rendition":
        values = [int(part or 0) for part in arguments.split(';')]
        state, index = self, 0
        while index < len(values):
            value = values[index]
            index += 1
            if value == 0:
                state = Rendition()
            elif value in (1, 2, 3, 4, 7):
                state = replace(state, attributes=tuple(sorted(set(state.attributes) | {value})))
            elif value in (22, 23, 24, 27):
                removed = {1, 2} if value == 22 else {value-20}
                state = replace(state, attributes=tuple(a for a in state.attributes if a not in removed))
            elif value in (39, 49):
                state = replace(state, **({'foreground': (0, 7)} if value == 39 else {'background': (0, 0)}))
            elif 30 <= value <= 37 or 90 <= value <= 97:
                state = replace(state, foreground=(0, value-30 if value < 90 else value-90+8))
            elif 40 <= value <= 47 or 100 <= value <= 107:
                state = replace(state, background=(0, value-40 if value < 100 else value-100+8))
            elif value in (38, 48):
                if index >= len(values):
                    raise AssertionError('missing extended SGR colour')
                mode = values[index]
                count = 1 if mode == 5 else 3 if mode == 2 else 0
                if not count or index+count >= len(values):
                    raise AssertionError('invalid extended SGR colour')
                colour = (1 if mode == 5 else 2, *values[index+1:index+1+count])
                state = replace(state, **({'foreground': colour} if value == 38 else {'background': colour}))
                index += count+1
            else:
                raise AssertionError(f'unhandled SGR attribute {value}')
        return state
