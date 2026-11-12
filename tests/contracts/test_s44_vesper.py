"""S44 part 3: Vesper's work closes to any Marked player (game design 7.3, #170).

Her board, her counter and her talk offers refuse with her canon line
(terminal UI 2.1). Accepted work is kept: it can't be advanced with her
until the Mark ends, and no deadline pauses.
"""

import pytest

from karst41.content.loader import ContentTree
from karst41.server import truce as truce_rules
from karst41.server.rules.combat import MARKED_SECONDS
from tests.contracts.test_broker_referrals import referral
from tests.test_dialogue_runtime import content, open_talker, press, setup  # noqa: F401 (fixture)

LINE = 'Vesper: "Not with that name. Come back in 15 min."'


def lattice_mark(game, player) -> None:
    """A Mark with no truce in it (interlock's channel writes marked_until)."""
    player.marked_until = truce_rules.iso(game.core.combat.now() + MARKED_SECONDS)


def toasts(game, caller) -> list[str]:
    return [frame.data["text"] for frame in game.frames_for(caller) if frame.type == "toast"]


def test_s44_vesper_board_counter_and_contract_board_refuse_any_mark(content: ContentTree) -> None:
    game, caller, player = setup(content)
    panels, commerce = game.core.contracts.panels, game.core.commerce
    assert panels.station(caller.session, 'vesper') == 'vesper'
    lattice_mark(game, player)
    with pytest.raises(ValueError, match='Not with that name'):
        panels.station(caller.session, 'vesper')
    with pytest.raises(ValueError, match='Not with that name'):
        commerce.vendor(caller.session, 'vesper')
    # The Halo contract board is hers too, wherever it stands.
    board = game.core.world.zones['sodium-tin-halo'].objects['halo-contract-board'].spec.tile
    from tests.character_helpers import place
    place(game, caller, 'sodium-tin-halo', (board[0] - 1, board[1] + 1))
    with pytest.raises(ValueError, match='Not with that name'):
        panels.station(caller.session, 'halo-contract-board')
    # The Halo's door is not hers: a non-truce Mark doesn't shut it.
    assert truce_rules.halo_refusal(game.core.loop.content, player, game.core.combat.now()) is None


@pytest.mark.parametrize('key', ['c', 'v'])
def test_s44_vesper_talk_offers_refuse_with_her_line(content: ContentTree, key: str) -> None:
    game, caller, player = setup(content)
    open_talker(game, caller)
    lattice_mark(game, player)
    game.frames_for(caller)
    press(game, caller, key)
    assert LINE in toasts(game, caller)
    assert caller.session.id not in game.core.contracts.panels.menus
    assert caller.session.id not in game.core.commerce.menus


def test_s44_open_board_closes_when_a_mark_lands(content: ContentTree) -> None:
    game, caller, player = setup(content)
    panels = game.core.contracts.panels
    from karst41.server.contracts.panels import Panel
    panels.menus[caller.session.id] = Panel(game.clock.now_tick(), 'vesper', 'vesper')
    game.step()
    assert caller.session.id in panels.menus
    lattice_mark(game, player)
    game.step()
    assert caller.session.id not in panels.menus


def test_s44_accepted_work_is_kept_and_its_deadline_still_runs(content: ContentTree) -> None:
    game, caller, player, owner, job = referral(content)
    proposal = owner.propose(player.id, owner.offer(job.id, player.id, 'vesper'), (player.id,), broker='vesper')
    owner.consent(proposal.id, player.id)
    owner.start(proposal.id, player.id)
    game.commit_commerce()
    instance = next(iter(owner.state.engine.instances.values()))
    # The referral story job has no deadline; give this instance one.
    instance.expires_at = deadline = owner.now() + 600
    lattice_mark(game, player)
    game.step(20)
    assert instance.state == 'active' and instance.expires_at == deadline  # Kept, not failed, no pause.
    with pytest.raises(ValueError, match='Not with that name'):
        owner.panels.station(caller.session, 'vesper')  # Can't be turned in with her meanwhile.
    assert deadline is not None
    assert instance.id in owner.state.engine.expire(deadline)
    assert instance.failure == 'expired'
