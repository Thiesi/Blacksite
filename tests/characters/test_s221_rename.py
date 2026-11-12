"""#221: the reserved gurney-number name form (game design 4 step 7).

A new name in the form is refused at the Wake. An existing character whose
name already falls under it chooses a new name at its next attach. Every
stored reference is keyed by id, so crews and market listings follow.
"""

from pathlib import Path
from typing import Any

import pytest

from karst41.content.loader import load_content
from karst41.server.items import make_item
from karst41.server.protocol import Frame
from karst41.server.rules import character as rules
from tests.character_helpers import act, create, place
from tests.harness import HeadlessServer


@pytest.fixture(scope='module')
def content() -> Any:
    return load_content(Path(__file__).parents[2]/'src/karst41/content')


def info(uid: int) -> dict[str, Any]:
    return {'user_id': uid, 'handle': f'Gurney{uid}', 'node_name': 'test'}


def reconnect(game: HeadlessServer, client: Any, uid: int) -> Any:
    game.core.sessions.disconnect(client.session)
    game.step(2)
    fresh = game.connect(info(uid))
    game.step(2)
    return fresh


def prompt(game: HeadlessServer, client: Any) -> Frame:
    frames = [f for f in game.frames_for(client) if f.type == 'prompt']
    assert frames, 'no prompt sent'
    return frames[-1]


def test_221_a_new_wake_cannot_choose_the_gurney_form(content: Any) -> None:
    game = HeadlessServer(content, character_state={})
    client = game.connect(info(1))
    game.step()
    act(game, client, Frame('intent', {'name': 'menu_cursor', 'args': {'delta': 1}}))
    act(game, client, Frame('intent', {'name': 'menu_select', 'args': {}}))
    wake = game.core.characters.wakes[client.session.id]
    for name in ('No. 0431', 'no-12', 'NO 7'):
        act(game, client, Frame('line', {'id': wake.prompt_id, 'text': name}))
        assert wake.stage == 'name' and wake.error == rules.GURNEY_TYPED
    act(game, client, Frame('line', {'id': wake.prompt_id, 'text': 'Noor'}))
    assert wake.stage == 'briefing' and wake.name == 'Noor'


@pytest.fixture
def legacy(content: Any) -> tuple[Any, ...]:
    """Two characters in one crew; the first lists an item, then is given a legacy gurney name."""
    game = HeadlessServer(content, character_state={})
    a, b = game.connect(info(1)), game.connect(info(2))
    create(game, a, name='Before', card='none')
    create(game, b, name='Taken', card='none')
    game.commit_commerce()
    crews = game.core.crews
    crews.perform(a.session, 'invite', b.session.player_id)
    crews.perform(b.session, 'accept', next(iter(crews.registry.invites)))
    player = game.core.characters.players[a.session.player_id]
    zone = game.core.world.zones['vatside-wake-hall']
    terminal = next(o.spec for o in zone.objects.values() if o.spec.kind == 'terminal')
    place(game, a, zone.id, game.core.world.free_tile(zone.id, terminal.tile))
    template = next(t for t in content.items.values() if t.class_ == 'weapon' and not t.no_vendor_sale)
    item = make_item(f'{game.core.sessions.origin}:item:{game.core.combat.next_serial()+1}', template,
                     player.id, game.clock.now_utc().isoformat())
    item.secured = False
    game.core.commerce.items[item.id] = item
    player.inventory.append(item.id)
    player.chits_bank = 1000
    game.core.market.execute(a.session, 'list', {'item': item.id, 'price': 50, 'buyout': 100,
                                                 'expiry': 86400, 'terminal': terminal.id})
    game.commit_commerce()
    listing = next(iter(game.core.market.market.listings.values()))
    player.name = 'No. 0431'  # Chosen before the reserved form existed.
    return game, a, b, player, listing


def test_221_legacy_gurney_name_must_be_renamed_and_references_follow(
        legacy: tuple[Any, ...], monkeypatch: pytest.MonkeyPatch) -> None:
    game, a, b, player, listing = legacy
    crew = game.core.crews.registry.crew_of(player.id)
    assert crew is not None
    # Today a logout leaves the crew. Canon's lasting roster (game design 10,
    # not built yet) keeps members across logout, so hold the membership to
    # show the id-keyed crew survives a rename.
    monkeypatch.setattr(game.core.crews.registry, 'remove', lambda pid: None)
    a = reconnect(game, a, 1)
    characters = game.core.characters
    assert characters.screens[a.session.id] == ('rename', 0) and a.session.player_id is None
    assert player.id not in {s.player_id for s in game.core.sessions.active.values() if s.player_id}
    ask = prompt(game, a)
    assert ask.data['id'] == 'rename:' + player.id
    body = characters.renaming[a.session.id]
    assert rules.gurney_rename('No. 0431') == 'No. 0431 reads as a gurney number now. Choose another name.'
    for text, error in (('Taken', 'That name is already in use. Choose another.'),
                        ('No 12', rules.GURNEY_TYPED), ('x', "Use 2-24 columns of letters, digits, spaces, - _ '.")):
        act(game, a, Frame('line', {'id': ask.data['id'], 'text': text}))
        assert characters.renaming[a.session.id] == (player.id, error) and player.name == 'No. 0431'
    act(game, a, Frame('line', {'id': ask.data['id'], 'text': 'After'}))
    assert player.name == 'After' and a.session.player_id == player.id
    assert a.session.id not in characters.renaming and a.session.id not in characters.screens
    assert game.core.world.actors[player.id].name == 'After'  # Any sleeper body is renamed too.
    assert player.record()['name_key'] == rules.name_key('After')
    saves = [e for e in game.commit_characters() if e['action'] == 'save' and e['player']['id'] == player.id]
    assert saves and saves[-1]['player']['name'] == 'After'
    # Crew and market are keyed by id; their views read the new name.
    assert game.core.crews.registry.crew_of(player.id) is crew
    assert any(row['id'] == player.id and row['name'] == 'After' for row in game.core.crews.roster(b.session.player_id))
    assert game.core.market.market.listings[listing.id].seller == player.id
    assert game.core.market.views.label(player.id).startswith('After / ')
    assert not characters.name_available('After') and characters.name_available('No. 0431') is True
    assert body == (player.id, '')


def test_221_cancelling_the_forced_rename_leaves_without_attaching(legacy: tuple[Any, ...]) -> None:
    game, a, _, player, _ = legacy
    a = reconnect(game, a, 1)
    act(game, a, Frame('intent', {'name': 'prompt_cancel'}))
    assert any(f.type == 'bye' for f in game.frames_for(a))
    assert player.name == 'No. 0431' and a.session.player_id is None
