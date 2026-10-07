"""S02: content invariants (01-entities.md section 5, 04-assets.md section 3)."""

from typing import Any

from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from tests.content.support import FIXTURE_WORLD, World, find


def only(world: World, *fragments: str) -> str:
    """Assert exactly one problem, containing every fragment; return it."""
    messages = world.messages()
    assert len(messages) == 1, messages
    for fragment in fragments:
        assert fragment in messages[0], messages[0]
    return messages[0]


def exits(d: dict) -> list[dict]:
    return d["exits"]


def control(d: dict) -> dict:
    return find(d["rooms"], "r-control")["controls"][0]


def test_fixture_is_clean() -> None:
    assert validate(load_content(FIXTURE_WORLD)) == []


# --- 01-entities.md section 5: exits ----------------------------------------


def test_exit_to_missing_zone(world: World) -> None:
    world.edit("zones/fx-street.json", lambda d: find(exits(d), "to-safe").update(target_zone="nowhere"))
    message = only(world, "content/zones/fx-street.json:", "exit to-safe", "'nowhere' does not exist")
    line = int(message.split(":")[1])
    assert '"id": "to-safe"' in world.path("zones/fx-street.json").read_text().splitlines()[line - 1]


def test_exit_onto_wall(world: World) -> None:
    world.edit("zones/fx-street.json", lambda d: find(exits(d), "to-safe").update(target_tile=[0, 0]))
    only(world, "exit to-safe", "target tile [0, 0] is not a passable tile in fx-safe")


def test_exit_tile_must_be_passable(world: World) -> None:
    world.edit("zones/fx-safe.json", lambda d: find(exits(d), "to-street").update(tile=[0, 10]))
    only(world, "exit to-street", "tile [0, 10] is not a passable tile in fx-safe")


# --- 01-entities.md section 5: cores ------------------------------------------


def test_control_to_missing_object(world: World) -> None:
    world.edit("cores/fx-core-a.json", lambda d: control(d)["target"].update(object="fx-street-nothing"))
    only(world, "control c-gate", "object 'fx-street-nothing' does not exist in fx-street")


def test_hardware_tile_must_be_hardware_object(world: World) -> None:
    world.edit("cores/fx-core-b.json", lambda d: d["hardware"][0].update(tile=[21, 10]))
    only(world, "content/cores/fx-core-b.json", "hardware tile fx-open [21, 10] is not a hardware object")


def test_shared_hardware_only_when_declared(world: World) -> None:
    # 01-gazetteer.md: lat-shaft alone has two hardware locations.
    second = {"zone": "fx-open", "tile": [20, 10]}
    world.edit("cores/fx-core-a.json", lambda d: d["hardware"].append(second))
    messages = world.messages()
    assert any("only lat-shaft may have two hardware locations" in m for m in messages)
    assert any("is also core 'fx-core-a'" in m for m in messages)  # fx-core-b's tile

    world.edit("cores/fx-core-a.json", lambda d: d["hardware"].pop())
    core = world.read("cores/fx-core-b.json") | {"id": "lat-shaft"}
    world.path("cores/fx-core-b.json").unlink()
    core["hardware"].append({"zone": "fx-street", "tile": [30, 3]})
    world.write("cores/lat-shaft.json", core)
    world.edit("bundles/fx-world.json", lambda d: d["members"]["cores"].remove("fx-core-b"))
    world.edit("sectors/fx-sector.json", lambda d: find(d["cells"], "c-core-b").update(core_id="lat-shaft"))
    # The declared two-location core is accepted; fx-core-a's tile is now shared.
    messages = world.messages()
    assert not any("only lat-shaft" in m for m in messages)
    assert any("hardware fx-street [30, 3] is also core 'fx-core-a'" in m for m in messages)

    core["hardware"][1] = {"zone": "fx-open", "tile": [20, 10]}
    world.write("cores/lat-shaft.json", core)
    assert any("must be in different zones" in m for m in world.messages())


def test_core_tier_and_training_exception(world: World) -> None:
    # 01-entities.md 1.4: tier 1-5, 0 only for the Wake training core.
    world.edit("cores/fx-core-b.json", lambda d: d.update(tier=0))
    only(world, "tier 0 is outside 1-5")
    world.edit("cores/fx-core-b.json", lambda d: d.update(tier=0, training=True))
    assert world.messages() == []
    world.edit("cores/fx-core-b.json", lambda d: d.update(tier=1, training=True))
    only(world, "the training core must be tier 0")


def test_core_room_count(world: World) -> None:
    # 00-game-design.md 6.2: a core has 3 to 12 rooms.
    def two_rooms(d: dict) -> None:
        d["rooms"] = d["rooms"][:2]
        d["rooms"][0]["neighbours"] = ["r-vault"]

    world.edit("cores/fx-core-b.json", two_rooms)
    only(world, "2 rooms; a core has 3-12")


def test_room_neighbours_symmetric(world: World) -> None:
    world.edit("cores/fx-core-b.json", lambda d: find(d["rooms"], "r-ice").update(neighbours=[]))
    only(world, "room r-entry: neighbour 'r-ice' does not list it back")


# --- control safety (01-entities.md 1.4, 00-game-design.md 6.4) ---------------


def test_route_control_needs_alternate_route(world: World) -> None:
    world.edit("cores/fx-core-a.json", lambda d: control(d).pop("alternate_route"))
    only(world, "control c-gate", "must name an alternate_route")


def test_control_closing_exit_needs_route_policy(world: World) -> None:
    world.edit("cores/fx-core-a.json", lambda d: control(d).update(safety_policy="none", alternate_route=None))
    only(world, "closes exit 'to-open-gate' but safety_policy is not 'route'")


def test_closing_only_way_out_is_rejected(world: World) -> None:
    # The street's only exit to the safe zone sits behind a controlled door.
    def door_on_to_safe(d: dict) -> None:
        d["objects"].append({"id": "fx-street-west", "tile": [1, 12], "kind": "door"})
        d["exits"] = [e for e in d["exits"] if e["id"] != "to-open-alley"]
    world.edit("zones/fx-street.json", door_on_to_safe)
    world.edit("cores/fx-core-a.json", lambda d: control(d).update(
        target={"zone": "fx-street", "object": "fx-street-west"}, alternate_route="to-open-gate"))
    messages = world.messages()
    assert any("control c-gate shut: fx-street can no longer reach an essential service" in m for m in messages)
    assert any("control c-gate shut: fx-open can no longer reach an essential service" in m for m in messages)


def test_essential_object_cannot_be_closed(world: World) -> None:
    world.edit("cores/fx-core-a.json", lambda d: control(d).update(
        target={"zone": "fx-safe", "object": "fx-safe-vat"}, action="disable", safety_policy="none",
        alternate_route=None))
    only(world, "cannot disable essential object 'fx-safe-vat'")


def test_hazard_control_rejected_in_safe_zone(world: World) -> None:
    world.edit("cores/fx-core-a.json", lambda d: control(d).update(
        target={"zone": "fx-safe", "object": "fx-safe-light"}, action="toggle", safety_policy="hazard",
        alternate_route=None, warning_seconds=5))
    only(world, "a hazard control cannot target a safe zone or pocket")


def test_owner_policy_cannot_hold_a_route(world: World) -> None:
    world.edit("cores/fx-core-a.json", lambda d: control(d).update(owner_policy=True))
    only(world, "owner_policy is not allowed")


def test_apartment_door_control_only_opens_vestibule(world: World) -> None:
    world.edit("zones/fx-street.json", lambda d: d["objects"].append(
        {"id": "fx-flat", "tile": [10, 20], "kind": "apartment_door"}))
    world.edit("cores/fx-core-a.json", lambda d: control(d).update(
        target={"zone": "fx-street", "object": "fx-flat"}, action="open", safety_policy="none",
        alternate_route=None))
    only(world, "an apartment door control may only open the private vestibule")
    world.edit("cores/fx-core-a.json", lambda d: control(d).update(scope="private_vestibule", permission="resident"))
    assert world.messages() == []


# --- assets ---------------------------------------------------------------------


def test_missing_text_asset(world: World) -> None:
    world.path("text/text-fx-gate-1.md").unlink()
    world.edit("bundles/fx-world.json", lambda d: d["members"].pop("text"))
    messages = world.messages()
    assert messages and all("text asset 'text-fx-gate-1' does not exist" in m for m in messages)
    sources = {m.split(":")[0] for m in messages}
    assert {"content/zones/fx-safe.json", "content/evidence.json", "content/events.json",
            "content/cores/fx-core-b.json"} <= sources


def test_art_needs_sidecar(world: World) -> None:
    world.path("art/art-fx-sigil.json").unlink()
    assert any("art needs a sidecar art-fx-sigil.json" in m for m in world.messages())


# --- factions (00-game-design.md 7.2) -------------------------------------------


def test_relations_complete(world: World) -> None:
    world.edit("factions.json", lambda d: find(d["factions"], "fx-beta").update(relations={}))
    messages = world.messages()
    assert any("relation to 'fx-alpha' is not defined" in m for m in messages)


def test_relations_asymmetry_must_be_declared(world: World) -> None:
    world.edit("factions.json", lambda d: d.update(asymmetries=[]))
    only(world, "relations fx-alpha/fx-beta differ by direction but are not declared")
    world.edit("factions.json", lambda d: (
        d.update(asymmetries=[["fx-alpha", "fx-beta"]]),
        find(d["factions"], "fx-beta").update(relations={"fx-alpha": "H"})))
    only(world, "asymmetry fx-alpha/fx-beta is declared but the relations are symmetric")


def test_faction_vat_must_be_vat_object(world: World) -> None:
    world.edit("factions.json", lambda d: find(d["factions"], "fx-alpha")["vat"].update(tile=[10, 5]))
    only(world, "vat fx-safe [10, 5] is not a vat object")


# --- zones (00-game-design.md 5.1, 04-assets.md 3) ------------------------------


def _resize(world: World, zone: str, width: int, height: int) -> None:
    rows = ["#" * width] + ["#" + "." * (width - 2) + "#" for _ in range(height - 2)] + ["#" * width]
    world.write_text(f"zones/{zone}.map", "\n".join(rows) + "\n")


def test_zone_size_limits(world: World) -> None:
    def strip(d: dict) -> None:
        d.update(exits=[], objects=[], spawners=[])
    for zone in ("fx-safe", "fx-street", "fx-open"):
        world.edit(f"zones/{zone}.json", strip)
    world.write("cores/fx-core-a.json", world.read("cores/fx-core-a.json") | {"hardware": []})
    _resize(world, "fx-open", 39, 20)
    _resize(world, "fx-safe", 200, 100)
    _resize(world, "fx-street", 201, 19)
    messages = [m for m in world.messages() if "zones are" in m]
    assert any(m.startswith("content/zones/fx-open.map") and "39x20" in m for m in messages)
    assert any("fx-street is 201x19" in m for m in messages)
    assert not any("fx-safe" in m for m in messages)


def test_object_on_impassable_tile(world: World) -> None:
    world.edit("zones/fx-safe.json", lambda d: find(d["objects"], "fx-safe-terminal").update(tile=[0, 5]))
    only(world, "object fx-safe-terminal: tile [0, 5] is not a passable tile")


def test_spawner_region_non_empty(world: World) -> None:
    world.edit("zones/fx-open.json", lambda d: d["spawners"][0].update(region={"x": 0, "y": 0, "w": 1, "h": 1}))
    only(world, "spawner fx-open-thugs: region is empty")


def test_pocket_only_in_contested_zone(world: World) -> None:
    world.edit("zones/fx-open.json", lambda d: d.update(pockets=[{"x": 30, "y": 2, "w": 2, "h": 2}]))
    only(world, "only contested zones have pockets")


def test_hazard_tile_rejected_in_pocket(world: World) -> None:
    rows = world.path("zones/fx-street.map").read_text().splitlines()
    rows[3] = rows[3][:4] + "!" + rows[3][5:]
    world.write_text("zones/fx-street.map", "\n".join(rows) + "\n")
    message = only(world, "content/zones/fx-street.map:4", "column 5: hazard tile 'hazard' in a safe zone or pocket")
    assert message


# --- terminal tables (03-terminal-ui.md sections 1 and 5) -----------------------


def test_palette_roles_complete(world: World) -> None:
    def damage(d: dict) -> None:
        del d["roles"]["wall"]
        del d["roles"]["floor"]["16"]
        del d["roles"]["cover"]["256"]["protan"]
        d["roles"]["water"]["16"]["default"] = 99
    world.edit("palette.json", damage)
    messages = world.messages()
    assert any("required role 'wall' is missing" in m for m in messages)
    assert any("palette role 'wall' does not exist" in m for m in messages)  # tiles.json
    assert any("role 'floor' has no 16 values" in m for m in messages)
    assert any("role 'cover' tier 256 has no protan value" in m for m in messages)
    assert any("role 'water' tier 16 default: 99 is not a 16 colour" in m for m in messages)


def test_glyph_must_be_cp437(world: World) -> None:
    world.edit("glyphs.json", lambda d: d["glyphs"].update(bad="✓"))
    only(world, "glyph 'bad'", "is not in CP437")


def test_tile_char_must_be_a_glyph(world: World) -> None:
    world.edit("glyphs.json", lambda d: d["glyphs"].pop("map-water"))
    only(world, "tile 'water': map char '~' is not in glyphs.json")


def test_keymap_key_conflict(world: World) -> None:
    def clash(d: dict) -> None:
        find(d["keymaps"], "vi")["bindings"]["fire"] = ["e"]
    world.edit("keymaps.json", clash)
    only(world, "keymap 'vi': key 'e' is bound to both 'fire' and 'interact'")


def test_keymap_binds_every_action(world: World) -> None:
    world.edit("keymaps.json", lambda d: find(d["keymaps"], "arrows")["bindings"].pop("help"))
    only(world, "keymap 'arrows' does not bind 'help'")


# --- items, ICE, programs (00-game-design.md 17) --------------------------------


def test_item_ids_unique_across_classes(world: World) -> None:
    world.edit("programs.json", lambda d: find(d["programs"], "prg_pick").update(id="ammo_9x"))
    world.edit("bundles/fx-world.json", lambda d: d["members"]["programs"].remove("prg_pick"))
    only(world, "id 'ammo_9x' is also used by items")


def test_item_class_block_required(world: World) -> None:
    world.edit("items.json", lambda d: find(d["items"], "con_sablier_patch").pop("consumable"))
    only(world, "class consumable needs a 'consumable' block")


def test_weapon_ammo_must_be_ammo(world: World) -> None:
    world.edit("items.json", lambda d: find(d["items"], "wpn_kestrel_sidearm")["weapon"].update(
        ammo="con_sablier_patch"))
    only(world, "ammo 'con_sablier_patch' is not an ammo item")


def test_ice_variant_must_be_compatible(world: World) -> None:
    # 00-game-design.md 12: Surge swaps non-black variants of equal or lower tier.
    world.edit("ice.json", lambda d: find(d["ice"], "ice_ticker").update(tier=2))
    only(world, "variant 'ice_ticker' is tier 2, above tier 1")
    world.edit("ice.json", lambda d: find(d["ice"], "ice_ticker").update(tier=1, black=True, meat_damage=5))
    only(world, "variant 'ice_ticker' is black ICE")


def test_black_ice_deals_meat_damage(world: World) -> None:
    world.edit("ice.json", lambda d: find(d["ice"], "ice_tripwire").update(black=True))
    only(world, "black ICE deals meat damage")


def test_program_names_have_no_aliases(world: World) -> None:
    world.edit("programs.json", lambda d: find(d["programs"], "prg_umbrella").update(name="Pick"))
    only(world, "programs have no aliases")


# --- contracts (00-game-design.md 9) --------------------------------------------


def _second_contract(world: World, change: Any) -> None:
    def add(d: dict) -> None:
        other = dict(d["contracts"][0])
        other["id"] = "fx-second-job"
        other["stages"] = [dict(st) for st in other["stages"]]
        change(other)
        d["contracts"].append(other)
    world.edit("contracts.json", add)


def test_receipt_keys_unique(world: World) -> None:
    _second_contract(world, lambda c: None)
    messages = world.messages()
    assert len(messages) == 2
    assert all("is also used by fx-first-job" in m for m in messages)


def test_branch_keys_unique(world: World) -> None:
    def branch(c: dict) -> None:
        for i, st in enumerate(c["stages"]):
            st["receipt_key"] = f"fx-second-job/{i}"
    world.edit("contracts.json", lambda d: d["contracts"][0].update(branch_group="fx-fork", branch="clinic"))
    _second_contract(world, lambda c: (branch(c), c.update(branch="clinic")))
    only(world, "branch fx-fork/clinic is also 'fx-first-job'")


def test_stage_target_must_resolve(world: World) -> None:
    world.edit("contracts.json", lambda d: d["contracts"][0]["stages"][1]["target"].update(control="c-none"))
    only(world, "stage s2: target: control 'c-none' does not exist in fx-core-a")


def test_clear_stage_declares_resolution(world: World) -> None:
    world.edit("contracts.json", lambda d: d["contracts"][0]["stages"][0].update(
        verb="clear", target={"kind": "npc", "npc": "fx-thug"}))
    only(world, "a clear stage declares lethal or subdue")


def test_unlock_condition_closed_set(world: World) -> None:
    world.edit("contracts.json", lambda d: d["contracts"][0].update(
        unlock_conditions=["standing_at_least fx-alpha 30", "lucky_day", "member_of fx-gamma"]))
    messages = world.messages()
    assert len(messages) == 2
    assert any("unknown condition 'lucky_day'" in m for m in messages)
    assert any("faction 'fx-gamma' does not exist" in m for m in messages)


# --- events and services (00-game-design.md 7.5, 12) ----------------------------


def test_event_hazard_rejected_in_safe_zone(world: World) -> None:
    world.edit("events.json", lambda d: d["events"][0]["effects"][0].update(
        zone="fx-safe", region={"x": 2, "y": 2, "w": 3, "h": 3}))
    only(world, "effect 0: a hazard cannot touch a safe zone or pocket")


def test_event_hazard_rejected_in_pocket(world: World) -> None:
    world.edit("events.json", lambda d: d["events"][0]["effects"][0].update(
        zone="fx-street", region={"x": 8, "y": 6, "w": 4, "h": 4}))
    only(world, "a hazard cannot touch a safe zone or pocket")


def test_event_hazard_needs_warning(world: World) -> None:
    world.edit("events.json", lambda d: d["events"][0]["effects"][0].update(warning_seconds=2))
    only(world, "a hazard needs at least 5 s warning")


def test_event_variant_cannot_strand_a_zone(world: World) -> None:
    world.edit("events.json", lambda d: d["events"][0]["variants"][0]["effects"][0].update(
        exits_closed=["fx-open/to-street-gate", "fx-open/to-street-alley"]))
    messages = world.messages()
    assert any("event fx-flare variant gate-held: fx-open can no longer reach an essential service" in m
               for m in messages)
    assert any("event fx-flare variant gate-held: fx-open has no way out" in m for m in messages)


def test_service_needs_common_and_reserve(world: World) -> None:
    world.edit("services.json", lambda d: d["services"][0]["allocations"].pop())
    only(world, "exactly one common and one reserve allocation")


def test_service_allocation_cannot_strand_a_zone(world: World) -> None:
    world.edit("services.json", lambda d: d["services"][0]["allocations"][1]["effects"].append(
        {"type": "route_hold", "zone": "fx-street", "exits_closed": ["fx-street/to-safe"]}))
    messages = world.messages()
    assert any("service fx-pump reserve: fx-street can no longer reach an essential service" in m
               for m in messages)


# --- dialogue (04-dramatis-personae.md Part III) --------------------------------


def _talker(**extra: Any) -> dict:
    return {
        "schema": 1, "id": "fx-recruiter", "name": "Fixture Recruiter", "faction": "fx-alpha",
        "lines": [
            {"id": "marked", "when": ["marked"], "text": "You have a mark on you."},
            {"id": "hello", "text": "Looking for work?"},
        ],
        "offers": [{"kind": "contract", "label": "Contract", "hotkey": "C", "ref": "fx-first-job"}],
        **extra,
    }


def test_dialogue_is_validated(world: World) -> None:
    world.write("dialogue/fx-recruiter.json", _talker())
    world.edit("npcs.json", lambda d: find(d["npcs"], "fx-recruiter").update(dialogue="fx-recruiter"))
    assert world.messages() == []

    talker = _talker()
    talker["lines"].reverse()
    talker["lines"][0]["text"] = "x" * 201
    talker["offers"].append({"kind": "vendor", "label": "Vendor", "hotkey": "c", "ref": "fx-nobody"})
    world.write("dialogue/fx-recruiter.json", talker)
    messages = world.messages()
    assert any("the last line is the fallback" in m for m in messages)
    assert any("longer than 200 characters" in m for m in messages)
    assert any("hotkey 'c' is not a unique single key" in m for m in messages)
    assert any("vendor 'fx-nobody' does not exist" in m for m in messages)


def test_machine_mind_needs_both_voices(world: World) -> None:
    talker = _talker(machine_mind=True, terminal=True)
    talker["lines"][0]["tag"] = "CUST"
    world.write("dialogue/fx-recruiter.json", talker)
    only(world, "a machine-mind talker needs a TEN line")


# --- seasons (00-game-design.md 13) ---------------------------------------------


def _season(**extra: Any) -> dict:
    return {
        "schema": 1, "number": 1, "title": "Fixture Season", "depth_target": 10000,
        "contribution_weights": {"data": 250, "salvage": 500, "key": 1000},
        "level": {"zone": "fx-open", "sector": "fx-sector"},
        "phases": ["approach", "seal", "decision"],
        "finale_choices": [
            {"id": "seal", "label": "Seal", "chronicle": "text-fx-gate-1", "balance_delta": -1,
             "standing": {"fx-alpha": 20}},
            {"id": "open", "label": "Open", "chronicle": "text-fx-gate-1", "balance_delta": 1},
        ],
        "finale_lines": [{"text": "text-fx-gate-1", "tag": "CUST"}, {"text": "text-fx-gate-1", "tag": "TEN"}],
        **extra,
    }


def test_season_finale_needs_both_voice_lines(world: World) -> None:
    world.write("seasons/1.json", _season())
    assert world.messages() == []
    world.write("seasons/1.json", _season(finale_lines=[{"text": "text-fx-gate-1", "tag": "CUST"}]))
    only(world, "the finale needs a guaranteed TEN line")


def test_season_ballot_and_checkpoint_keys_unique(world: World) -> None:
    season = _season(phases=["approach", "approach"])
    season["finale_choices"][1]["id"] = "seal"
    world.write("seasons/1.json", season)
    messages = world.messages()
    assert any("phase (checkpoint) ids are not unique" in m for m in messages)
    assert any("finale choice (ballot) ids are not unique" in m for m in messages)


def test_season_file_name_is_its_number(world: World) -> None:
    world.write("seasons/2.json", _season())
    assert any("file name must be 1.json" in m for m in world.messages())


# --- bundles (02-architecture.md 15.3) ------------------------------------------


def _authoring_job(world: World) -> None:
    world.edit("contracts.json", lambda d: d["contracts"].append({
        "id": "fx-future-job", "faction": "vesper", "type": "fetch", "story": True, "season": 2,
        "stages": [{"id": "s1", "verb": "fetch", "input": "carry", "completion": "delivered",
                    "receipt_key": "fx-future-job/s1",
                    "target": {"kind": "item", "item": "story_not_written_yet"}}],
    }))


def test_authoring_bundle_may_dangle(world: World) -> None:
    _authoring_job(world)
    assert any("story_not_written_yet" in m for m in world.messages())
    world.write("bundles/fx-future.json", {
        "schema": 1, "id": "fx-future", "status": "authoring", "depends": ["fx-world"],
        "members": {"contracts": ["fx-future-job"], "items": ["story_not_written_yet"]},
    })
    assert world.messages() == []


def test_active_content_cannot_reference_authoring_content(world: World) -> None:
    _authoring_job(world)
    world.write("bundles/fx-future.json", {
        "schema": 1, "id": "fx-future", "status": "authoring",
        "members": {"contracts": ["fx-future-job"]},
    })
    world.edit("factions.json", lambda d: find(d["factions"], "fx-alpha")["contracts"].append("fx-future-job"))
    only(world, "content/factions.json", "contract 'fx-future-job' is in an authoring bundle")


def test_active_bundle_rules(world: World) -> None:
    world.write("bundles/fx-future.json", {
        "schema": 1, "id": "fx-future", "status": "authoring", "depends": ["fx-world"],
        "members": {"zones": ["fx-safe"]},
    })
    world.edit("bundles/fx-world.json", lambda d: d.update(depends=["fx-future", "fx-missing"]))
    messages = world.messages()
    assert any("zones 'fx-safe' is already in bundle" in m for m in messages)
    assert any("active bundle depends on authoring bundle 'fx-future'" in m for m in messages)
    assert any("depends on missing bundle 'fx-missing'" in m for m in messages)
    assert any("bundle dependencies form a cycle" in m for m in messages)


def test_active_bundle_members_must_exist(world: World) -> None:
    world.edit("bundles/fx-world.json", lambda d: d["members"]["npcs"].append("fx-ghost"))
    only(world, "member npcs 'fx-ghost' does not exist")
