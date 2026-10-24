"""World-event schedules and bounded modifiers, game design section 12."""

from types import MappingProxyType

ROLL_SECONDS = 20 * 60
ADVANCE_SECONDS = 60 * 60
MAX_RESERVED = 2
WARNING_SECONDS = 5
BEACON_SECONDS = 5 * 60
SURGE_MAGNITUDE = 1.3
CURFEW_HEAT = 2
EXHALE_RATE = 3
ESCORT_RADIUS = 6  # Game 12: same proximity as guarding in game 10.

# Duration, cooldown and default weight, exactly game design section 12.
SCHEDULES = MappingProxyType({
    'ring-fall': (20 * 60, 90 * 60, 5),
    'curfew': (60 * 60, 4 * 60 * 60, 2),
    'choir-surge': (15 * 60, 3 * 60 * 60, 2),
    'exhale': (30 * 60, 2 * 60 * 60, 3),
    'convoy': (25 * 60, 60 * 60, 4),
})
