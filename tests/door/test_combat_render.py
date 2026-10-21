"""Combat views at both terminal sizes and all colour tiers."""

from dataclasses import replace
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.door.model import Display
from blacksite.server.protocol import Frame, encode
from tests.character_helpers import create, place
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer


@pytest.mark.parametrize("width,height",[(80,24),(132,50)])
@pytest.mark.parametrize("tier",["16","256","truecolor"])
def test_target_hit_flash_and_dead_screen_keep_log_width_safe(info,repo_root: Path,width,height,tier) -> None:
    game=HeadlessServer(load_content(repo_root/"src/blacksite/content"),character_state={})
    clients=[]
    for uid,x in ((1,25),(2,27)):
        client=game.connect({"user_id":uid,"handle":f"BBS界{uid}","node_name":"test"},width=width,height=height)
        create(game,client,archetype=0,name=f"Runner界{uid}",card="none")
        game.core.characters.players[client.session.player_id].grade=5
        place(game,client,"vatside-clinics",(x,3));clients.append(client)
    a,b=clients
    engine=game.core.combat
    actor=engine.actor(game.core.characters.players[a.session.player_id])
    other=engine.actor(game.core.characters.players[b.session.player_id])
    actor.target=other.id
    display=Display(replace(info,width=width,height=height,color_depth=tier))
    terminal=FakeTerminal(width,height)
    stamp=0
    def draw() -> str:
        nonlocal stamp
        stamp+=1
        game.step()
        for frame in game.frames_for(a): encode(frame);display.receive(frame,stamp)
        display.toast=None
        terminal.write(display.render(stamp)[0])
        return terminal.screen_text()
    screen=draw()
    assert "TARGET" in screen and "Runner界2" in screen and "HP ######## 100%" in screen
    normal=terminal.styles[(0,0)]
    engine.hurt(other,actor,5)
    draw()
    assert terminal.styles[(0,0)]!=normal
    terminal.write(display.render(stamp+.2)[0])
    assert terminal.styles[(0,0)]==normal
    engine.hurt(other,actor,1000)
    draw();game.step(50);game.commit_commerce()
    screen=draw()
    assert "SABLIER DECANT" in screen and "Clone charge" in screen
    assert "hits you" in screen
    a.send(Frame("intent",{"name":"menu_close","args":{}}));game.step()
    assert game.core.characters.players[a.session.player_id].progress["combat"]["stage"]=="dead"


def test_vi_movement_and_sitrep_bindings_are_preserved(repo_root: Path) -> None:
    tree=load_content(repo_root/"src/blacksite/content")
    vi=next(m for m in tree.keymaps.keymaps if m.id=="vi")
    assert "h" in vi.bindings["move_left"] and "H" in vi.bindings["sprint_left"]
    assert "w" in vi.bindings["sitrep"]
    assert vi.bindings["weapon_cycle"]==("x","X")


def test_ability_menu_close_returns_full_zone_then_quick_key_casts(info,repo_root: Path) -> None:
    game=HeadlessServer(load_content(repo_root/"src/blacksite/content"),character_state={})
    client=game.connect();create(game,client,archetype=2,name="Cantor",card="none")
    display=Display(info)
    def receive() -> None:
        for frame in game.frames_for(client): assert display.receive(frame,game.clock.now_tick())==[]
    receive()
    client.send(Frame("key",{"k":"v","t":0}));game.step();receive()
    assert display.kind=="menu"
    for frame in display.key("1",1): client.send(frame)
    game.step();receive()
    for frame in display.key("escape",2): client.send(frame)
    game.step();receive()
    assert display.kind=="zone" and not display.resync_pending
    for frame in display.key("1",3): client.send(frame)
    game.step(6)
    actor=game.core.characters.sim.avatars[client.session.user_id].actor
    assert actor.cooldowns["ability:hymn_steady"]>game.clock.now_tick()
