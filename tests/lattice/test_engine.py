"""Design 6.1/5.2: real multi-session core, deterministic ticks, no sockets."""

from dataclasses import replace
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.server.items import make_item
from blacksite.server.protocol import Frame, encode
from blacksite.server.world.movement import move
from tests.character_helpers import act, create, place, state
from tests.harness import ADMIN_SECRET, HeadlessServer, hello


@pytest.fixture
def runners(repo_root: Path):
    content = load_content(repo_root/"src/blacksite/content")
    # Isolated rule scenarios; live acceptance keeps all city traffic.
    content.zones = {k: replace(z, meta=replace(z.meta, spawners=(),
        objects=tuple(obj for obj in z.meta.objects if obj.kind != 'salvage_field')))
        for k, z in content.zones.items()}
    game = HeadlessServer(content, character_state={})
    clients = []
    for uid, pos in ((1, (30, 5)), (2, (31, 6)), (3, (32, 5))):
        client = game.connect({"user_id": uid, "handle": f"Wide界{uid}", "node_name": "test"})
        create(game, client, archetype=0, name=f"Runner{uid}", card="none")
        place(game, client, "core-plaza", pos)
        clients.append(client)
        for other in clients:
            game.frames_for(other)
    return game, *clients


def actor(game, client):
    return game.core.characters.sim.avatars[client.session.user_id].actor


def jack(game, client):
    act(game, client, Frame("key", {"k": "j", "t": 0}))
    game.step(3)
    game.commit_commerce()  # S16's first authored entrance-cell receipt.
    return game.core.lattice.presences[client.session.player_id]


def intent(game, client, name, **args):
    act(game, client, Frame("intent", {"name": name, "args": args}))


def test_design_6_1_two_runners_body_subscription_and_public_loan(runners):
    game, a, b, c = runners
    lattice = game.core.lattice
    original = actor(game, a).position
    presence = jack(game, a)
    assert actor(game, a).stance == "jacked" and actor(game, a).position == original
    assert actor(game, a).zone == "core-plaza" and a.session.subscribed == "lat-core"
    assert presence.rig == ("prg_pick", "prg_umbrella", None)
    assert presence.integrity == 100 and presence.trace == 0
    frames = game.frames_for(b)
    zone = [f.data["body"] for f in frames if f.type == "view" and f.data["kind"] == "zone"][-1]
    body = next(row for row in zone["actors"] if row["id"] == a.session.player_id)
    assert body["stance"] == "jacked" and body["glyph"] == "▒"
    jack(game, b)
    view = lattice.view(a.session, presence)
    assert [p["name"] for p in view["presences"]] == ["Runner2"]
    assert view["body_safety"] == "safe"
    assert len(game.core.world.actors) == 3 and len(lattice.presences) == 2
    intent(game, a, "lat.jack_out")
    assert a.session.player_id not in lattice.presences and actor(game, a).stance == "normal"
    assert a.session.subscribed == "core-plaza" and actor(game, a).position == original
    game.step(3)
    assert a.session.id not in lattice.sim.external_views


def test_design_5_2_jacked_body_cannot_move_act_or_evade(runners):
    game, a, b, c = runners
    jack(game, a)
    body = actor(game, a)
    before = body.position
    assert game.core.combat.evasion(body) == 0
    assert not move(body, game.core.world.zones[body.zone], "down", game.clock.now_tick())
    for name in ("fire", "ability", "inv.drop", "use_slot", "stance", "sprint"):
        intent(game, a, name, target=actor(game, b).id, dir="down", slot="1")
    assert body.position == before and body.stance == "jacked"
    assert not game.core.commerce.outbox and not game.core.commerce.ready(a.session)
    assert not game.core.combat.legal(body, actor(game, b))
    logs = [line["text"] for f in game.frames_for(a) if f.type == "log" for line in f.data["lines"]]
    assert any("Your body cannot act here. J returns" in line for line in logs)


def test_design_6_1_traversal_deadline_gate_hidden_and_cross_sector(runners):
    game, a, b, c = runners
    lattice = game.core.lattice
    presence = jack(game, a)
    start = presence.cell
    intent(game, a, "move", dir="right")
    assert presence.cell == start and presence.destination
    remaining = presence.move_until-game.clock.now_tick()
    game.step(remaining-1)
    assert presence.cell == start
    game.step()
    assert presence.cell != start
    source = lattice.sectors.cells[presence.sector][presence.cell]
    assert source.uplink
    intent(game, a, "lat.move", sector=source.uplink.sector, cell=source.uplink.cell)
    game.step(presence.move_until-game.clock.now_tick())
    assert presence.sector == source.uplink.sector and a.session.subscribed == presence.sector
    # Use actual gated/hidden adjacency without granting access.
    sid = presence.sector
    gated = next(cell for cell in lattice.sectors.records[sid].cells if cell.access_kind == "gated")
    presence.cell = gated.neighbours[0]
    intent(game, a, "lat.move", cell=gated.id)
    assert presence.destination is None and presence.cell != gated.id
    logs = [line["text"] for f in game.frames_for(a) if f.type == "log" for line in f.data["lines"]]
    assert any("requires key program tier 2" in line for line in logs)
    hidden = next(cell for cell in lattice.sectors.records[sid].cells if cell.access_kind == "hidden")
    presence.cell = hidden.neighbours[0]
    view = lattice.view(a.session, presence)
    assert hidden.id not in {cell["id"] for cell in view["cells"]}
    assert all(hidden.id not in (edge["a"], edge["b"]) for edge in view["edges"])
    intent(game, a, "lat.move", cell=hidden.id)
    assert presence.destination is None
    assert lattice.reveal(game.core.characters.players[presence.player_id], sid, hidden.id)
    intent(game, a, "lat.move", cell=hidden.id)
    game.step(presence.move_until-game.clock.now_tick())
    assert presence.cell == hidden.id
    assert hidden.id in {cell["id"] for cell in lattice.view(a.session, presence)["cells"]}


def test_design_6_1_gated_escape_bounded_interruptions_and_recovery(runners):
    game, a, b, c = runners
    lattice = game.core.lattice
    presence = jack(game, a)
    presence.cell = next(cell.id for cell in lattice.sectors.records[presence.sector].cells if cell.access_kind == "gated")
    presence.integrity = 40
    intent(game, a, "lat.jack_out")
    assert presence.escape and presence.player_id in lattice.presences
    body = actor(game, a)
    for _ in range(3):
        game.step(5)
        body.behaviour["hit_serial"] = int(body.behaviour.get("hit_serial", 0))+1
        game.step()
    assert presence.escape.interruptions == 3
    deadline = presence.escape.until_tick
    while game.clock.now_tick() < deadline:
        body.behaviour["hit_serial"] += 1
        game.step()
    assert presence.player_id not in lattice.presences and body.stance == "normal"
    player = game.core.characters.players[presence.player_id]
    game.step(20)
    assert lattice.integrity(player) == 50
    # Offline recovery uses persisted injected UTC, not a reset on login.
    saved = state(game)
    later = HeadlessServer(game.core.loop.content, character_state=saved, clock=game.clock)
    game.clock.advance(100)
    assert later.core.lattice.integrity(later.core.characters.players[player.id]) == 100


def test_design_6_1_disconnect_and_physical_down_remove_presence(runners):
    game, a, b, c = runners
    presence = jack(game, a)
    game.core.sessions.disconnect(a.session)
    assert presence.player_id not in game.core.lattice.presences
    assert actor(game, a).stance != "jacked"
    jack(game, b)
    body = actor(game, b)
    body.health = 0
    body.stance = "down"
    player = game.core.characters.players[body.id]
    player.progress["combat"] = {"stage": "down", "until": game.clock.now_utc().timestamp()+30, "killer": "test"}
    game.step()
    assert body.id not in game.core.lattice.presences
    assert game.core.characters.sim.external_views[b.session.id][0] == "dead"


def test_design_6_1_rig_access_and_vi_keymap(runners):
    game, a, b, c = runners
    place(game, a, "core-plaza", (40, 20))
    intent(game, a, "lat.jack_in")
    assert a.session.player_id not in game.core.lattice.presences
    player = game.core.characters.players[a.session.player_id]
    item = make_item("test:rig", game.core.loop.content.items["item_rig_portable_ow_brick"], player.id,
                     game.clock.now_utc().isoformat())
    player.inventory.append(item.id)
    game.core.characters.items[item.id] = item
    game.core.characters.item_templates[item.id] = item.template
    presence = jack(game, a)
    assert len(presence.rig) == 3
    a.session.keymap_id = "vi"
    assert "Ctrl-O jack out" in game.core.lattice.view(a.session, presence)["hint"]
    start = presence.cell
    act(game, a, Frame("key", {"k": "j", "t": 0}))
    assert presence.player_id in game.core.lattice.presences
    assert presence.destination and presence.cell == start
    act(game, a, Frame("key", {"k": "ctrl-o", "t": 0}))
    assert presence.player_id not in game.core.lattice.presences


def test_design_11_lattice_chat_and_emotes_have_separate_audiences(runners):
    game, a, b, c = runners
    jack(game, a); jack(game, b)
    for client in (a, b, c): game.frames_for(client)
    intent(game, a, "chat", channel="say", text="cell hello")
    lines = lambda client: [line for f in game.frames_for(client) if f.type == "log" for line in f.data["lines"]]
    assert any(line["channel"] == "lat" and "cell hello" in line["text"] for line in lines(b))
    assert not any("cell hello" in line["text"] for line in lines(c))
    intent(game, c, "emote", id="wave", target="Runner1")
    assert not any("waves" in line["text"] for line in lines(a))


def test_design_6_1_admin_who_is_operator_only(runners):
    game, a, b, c = runners
    presence = jack(game, a)
    operator = game.connect(frame=hello({"bbs_user_id": "operator", "handle": "operator"}, secret=ADMIN_SECRET))
    act(game, operator, Frame("admin.lattice.who"))
    views = [f for f in game.frames_for(operator) if f.type == "view"]
    assert presence.cell in views[-1].data["body"]["lines"][0]
    b.send(Frame("admin.lattice.who"))
    assert b.session.closed


def test_design_11_sitrep_returns_to_lattice_without_activating_body(runners):
    game, a, b, c = runners
    presence = jack(game, a)
    before = actor(game, a).position
    act(game, a, Frame("key", {"k": "w", "t": 0}))
    assert a.session.id in game.core.chat.sitreps
    assert game.core.characters.sim.external_views[a.session.id][0] == "menu"
    intent(game, a, "inv.use", item="anything")
    assert not game.core.commerce.outbox
    intent(game, a, "menu_close")
    assert game.core.characters.sim.external_views[a.session.id][0] == "lattice"
    assert game.core.lattice.presences[a.session.player_id] is presence
    assert actor(game, a).position == before and actor(game, a).stance == "jacked"


def test_design_6_1_ghost_native_and_credential_revocation_at_arrival(runners):
    game, a, b, c = runners
    player = game.core.characters.players[a.session.player_id]
    player.archetype = "ghost"
    player.rig = {"native": True, "slots": ["prg_pick", "prg_umbrella", None]}
    place(game, a, "core-plaza", (40, 20))
    presence = jack(game, a)
    assert len(presence.rig) == 3
    lattice = game.core.lattice
    presence.sector = "lat-scour"
    target = next(c for c in lattice.sectors.records["lat-scour"].cells if c.kind == "descent")
    presence.cell = target.neighbours[0]
    lattice.events.add("ring-fall")
    intent(game, a, "lat.move", cell=target.id)
    assert presence.destination
    lattice.events.clear()
    game.step(presence.move_until-game.clock.now_tick())
    assert presence.cell != target.id and presence.destination is None


def test_design_6_1_debug_reveal_is_scoped_and_audited(runners):
    game, a, b, c = runners
    presence = jack(game, a)
    lattice = game.core.lattice
    hidden = next(cell.id for cell in lattice.sectors.records[presence.sector].cells if cell.access_kind == "hidden")
    operator = game.connect(frame=hello({"bbs_user_id": "operator", "handle": "operator"}, secret=ADMIN_SECRET))
    audit = []
    game.core.audit = audit.append
    data = {"player": presence.player_id, "sector": presence.sector, "cell": hidden}
    act(game, operator, Frame("admin.lattice.reveal", data))
    assert hidden in lattice.found(game.core.characters.players[presence.player_id], presence.sector)
    assert hidden not in lattice.found(game.core.characters.players[b.session.player_id], presence.sector)
    assert audit[-1]["target"] == data and audit[-1]["outcome"] == "ok"
    act(game, operator, Frame("admin.lattice.reveal", {**data, "cell": "missing"}))
    assert audit[-1]["outcome"] == "unavailable"


def test_design_6_1_jack_waits_for_real_pending_transfer(runners):
    game, a, b, c = runners
    player = game.core.characters.players[a.session.player_id]
    item = next(game.core.characters.items[iid] for iid in player.inventory
                if not game.core.characters.items[iid].secured and not game.core.characters.items[iid].bound)
    intent(game, a, "inv.drop", item=item.id)
    assert game.core.commerce.pending and game.core.commerce.outbox
    intent(game, a, "lat.jack_in")
    assert player.id not in game.core.lattice.presences
    assert actor(game, a).stance == "normal"
    game.commit_commerce()
    jack(game, a)
    assert actor(game, a).stance == "jacked"


def test_architecture_11_moving_lattice_deltas_fit_budget_and_menu_return(runners):
    game, a, b, c = runners
    presence = jack(game, a)
    game.frames_for(a)
    a.session.acknowledge(a.session.view_revision)
    a.send(Frame("intent", {"name": "move", "args": {"dir": "right"}}))
    sizes = []
    while True:
        game.step()
        frames = [f for f in game.frames_for(a) if f.type in ("view", "delta")]
        for frame in frames:
            assert frame.type == "delta"
            sizes.append(len(encode(frame)))
            a.session.acknowledge(frame.data["rev"])
        if presence.destination is None:
            break
    assert sizes and max(sizes) <= 2048  # Architecture 11 typical update.
    act(game, a, Frame("key", {"k": "w", "t": 0}))
    menu = [f for f in game.frames_for(a) if f.type == "view"][-1]
    assert menu.data["kind"] == "menu"
    a.session.acknowledge(menu.data["rev"])
    intent(game, a, "menu_close")
    resumed = [f for f in game.frames_for(a) if f.type in ("view", "delta")][-1]
    assert resumed.type == "view" and resumed.data["kind"] == "lattice"
    assert resumed.data["body"]["me"]["cell"] == presence.cell
    a.session.acknowledge(resumed.data["rev"])
    intent(game, a, "resync")
    resync = [f for f in game.frames_for(a) if f.type == "view"][-1]
    assert resync.data["kind"] == "lattice"


def test_terminal_e_preserves_nearby_counter_and_explicit_jack(runners):
    game, a, b, c = runners
    place(game, a, "vatside-wake-hall", (34, 15))
    assert game.core.lattice.terminal(actor(game, a))
    act(game, a, Frame("key", {"k": "e", "t": 0}))
    assert a.session.player_id not in game.core.lattice.presences
    assert game.core.commerce.menus[a.session.id].kind == "vendor"
    intent(game, a, "menu_close")
    jack(game, a)
    assert actor(game, a).stance == "jacked"
