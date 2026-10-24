"""Pure talker selection and bark scheduling (game 13.4, entities 1.11).

The adapter supplies committed facts, a zone RNG and ticks. Selecting a
line neither changes the player nor grants an offered action.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from random import Random

from blacksite.content.schema import Bark, DialogueLine, DialogueNode, Offer
from blacksite.server.clock import TICK_HZ

BARK_RADIUS = 6  # Game 13.4: nearby audience, measured by the adapter.
DEFAULT_BARK_SECONDS = 90  # Game 13.4; content can specify its own interval.
OPPOSING_SKIP = .7  # Game 13.4: balances one and two.
EXTREME_OPPOSING_SKIP = .9  # Game 13.4: balance three.

Talker = DialogueNode


@dataclass(frozen=True)
class Facts:
    """One viewer's committed state, with no unpublished world proposals."""

    grade: int = 1
    archetype: str = 'hardline'
    faction: str | None = None
    standing: Mapping[str, int] = field(default_factory=dict)
    legal: bool = False
    marked: bool = False
    enemy: bool = False
    balance: int = 0
    met: frozenset[str] = frozenset()
    items: frozenset[str] = frozenset()
    contracts: Mapping[str, int] = field(default_factory=dict)
    completed: frozenset[str] = frozenset()
    evidence: frozenset[str] = frozenset()
    receipts: frozenset[str] = frozenset()
    services: Mapping[str, str] = field(default_factory=dict)
    season_stage: str = 'open'
    chronicle: Mapping[int, str] = field(default_factory=dict)
    events: frozenset[str] = frozenset()


def condition(text: str, talker: Talker, facts: Facts) -> bool:
    """Evaluate the validated closed condition set from entities 1.11."""
    name, *args = text.split()
    if name == 'first_meeting':
        return talker.id not in facts.met
    if name in ('grade_below', 'grade_at_least'):
        return facts.grade < int(args[0]) if name == 'grade_below' else facts.grade >= int(args[0])
    if name == 'is_wake':
        return not facts.legal
    if name in ('standing_below', 'standing_at_least'):
        value = facts.standing.get(args[0], 0)
        return value < int(args[1]) if name == 'standing_below' else value >= int(args[1])
    if name in ('member_of', 'not_member_of'):
        return facts.faction == args[0] if name == 'member_of' else facts.faction != args[0]
    if name == 'enemy_of_me':
        return facts.enemy
    if name in ('marked', 'not_marked'):
        return facts.marked if name == 'marked' else not facts.marked
    if name == 'has_contract':
        return args[0] in facts.contracts
    if name == 'contract_stage':
        return facts.contracts.get(args[0]) == int(args[1])
    if name == 'completed_contract':
        return args[0] in facts.completed
    if name == 'has_item':
        return args[0] in facts.items
    if name == 'season_stage':
        return facts.season_stage == args[0]
    if name == 'chronicle_choice':
        return facts.chronicle.get(int(args[0])) == args[1]
    if name == 'event_active':
        return args[0] in facts.events
    if name == 'archetype':
        return facts.archetype == args[0]
    if name == 'balance':
        return args[0] == ('CUST' if facts.balance < 0 else 'TEN' if facts.balance > 0 else 'EVEN')
    if name == 'has_evidence':
        return args[0] in facts.evidence
    if name == 'receipt':
        return args[0] in facts.receipts
    if name == 'service_state':
        return facts.services.get(args[0]) == args[1]
    if name in ('legal', 'not_legal'):
        return facts.legal if name == 'legal' else not facts.legal
    raise ValueError(f'Unknown dialogue condition: {name}')


def matches(conditions: tuple[str, ...], talker: Talker, facts: Facts) -> bool:
    return all(condition(text, talker, facts) for text in conditions)


def evaluate(talker: Talker, facts: Facts, rng: Random) -> DialogueLine:
    """First eligible line, with optional opposing voice weighting only."""
    for line in talker.lines:
        if not matches(line.when, talker, facts):
            continue
        opposing = (line.tag == 'CUST' and facts.balance > 0
                    or line.tag == 'TEN' and facts.balance < 0)
        if opposing and not line.required:
            skip = EXTREME_OPPOSING_SKIP if abs(facts.balance) >= 3 else OPPOSING_SKIP
            if rng.random() < skip:
                continue
        return line
    raise ValueError(f'Talker {talker.id} has no eligible fallback line')


def eligible_offers(talker: Talker, facts: Facts) -> tuple[Offer, ...]:
    return tuple(offer for offer in talker.offers if matches(offer.when, talker, facts))


@dataclass
class BarkScheduler:
    """Per-talker deadlines; ticking or inspecting alone never emits text."""

    next_due: dict[str, int] = field(default_factory=dict)

    def choose(self, talker: Talker, tick: int, rng: Random, *,
               nearby: bool, interacting: bool) -> Bark | None:
        if (not nearby or interacting or not talker.barks
                or tick < self.next_due.get(talker.id, 0)):
            return None
        bark = rng.choices(talker.barks, weights=[b.weight for b in talker.barks], k=1)[0]
        self.next_due[talker.id] = tick+bark.min_interval_seconds*TICK_HZ
        return bark
