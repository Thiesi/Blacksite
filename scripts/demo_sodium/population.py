"""Demo only: Sodium Row and Tin Halo population (#143 sections 3, 4 and 6).

The creative consultant's population for the never-merged demo branch
``demo/sodium-row-evening``: off-duty crowds by custom in each bar, Sable's
card court, Mira Solenne, Dolf behind the Halo's bar, bar counters that sell
drinks, and the speech for all of them. Geometry is frozen (b7a2b68) and this
script never touches a ``.map`` file or ``geometry.py``'s output beyond the
spawner and object-param keys named below.

Idempotent: run it again and it rewrites the same records.

    python scripts/demo_sodium/population.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "src" / "blacksite" / "content"

# Hub population numbers (game design 5.5: grade 1, Frame/Nerve/Vitals 20,
# Cortex 10, Resonance 5, 60 s respawn).
ATTRS = {"frame": 20, "nerve": 20, "cortex": 10, "resonance": 5, "vitals": 20}
RESPAWN = 60


def load(rel: str):
    return json.loads((CONTENT / rel).read_text(encoding="utf-8"))


def save(rel: str, data) -> None:
    (CONTENT / rel).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")


def line(lid: str, text: str, *when: str) -> dict:
    return {"id": lid, "text": text, "when": list(when), "required": True}


def bark(text: str) -> dict:
    return {"text": text, "weight": 1, "min_interval_seconds": 90}


def talker(did: str, name: str, faction, title: str, lines, barks=()) -> dict:
    return {"schema": 1, "id": did, "name": name, "faction": faction, "title": title,
            "terminal": False, "machine_mind": False, "lines": list(lines),
            "offers": [], "barks": list(barks)}


# --- Speech ---------------------------------------------------------------
# Voice rules: second person where narrating, short sentences, no em-dashes,
# no "cyberpunk", "hacker" or "cyberspace". Nothing here discloses a secret:
# nobody says Vesper arranged the truce (personae: she wants nobody to know).

DIALOGUE = {
    "row-halvard-offduty": talker(
        "row-halvard-offduty", "Halvard staff, off duty", "halvard", "Upstairs regular", [
            line("member", "Sit with us. Nobody here asks about your shift, and nobody upstairs asks about this bar.", "member_of halvard"),
            line("enemy", "Truce, friend. I drink here so I don't have to see you anywhere else.", "enemy_of_me"),
            line("wake", "A Wake on the Row. Stay near the Stair. That's what we do.", "is_wake"),
            line("greeting", "Best glass on the Row and the shortest walk home. You pay for both."),
        ], [bark("Two flights up and you're back under Warden blue. That's the whole charm."),
            bark("Ring's bright tonight. Somebody's salvage bill just went up.")]),
    "row-sablier-offduty": talker(
        "row-sablier-offduty", "Sablier staff, off duty", "sablier", "Upstairs regular", [
            line("member", "Clinic shift ended an hour ago. Don't make me look at anything.", "member_of sablier"),
            line("enemy", "Truce. I patch your kind on Tuesdays. Tonight I'm drinking.", "enemy_of_me"),
            line("wake", "Vantongeren's? Keep that lease paper dry. The Row is wet.", "is_wake"),
            line("greeting", "We sit by the window so the Row can see we're fine. We are fine."),
        ], [bark("Upstairs closes when the last of us remembers the Stair.")]),
    "row-kestrel-crew": talker(
        "row-kestrel-crew", "Kestrel crew, off shift", "kestrel", "Long Shift regular", [
            line("member", "Shift's on the board, drinks are on the slate. Sit, you're blocking the door.", "member_of kestrel"),
            line("enemy", "You're Sable's problem tonight, not mine. Hands on the bar.", "enemy_of_me"),
            line("veteran", "You've got the look of somebody who's been shot at. Gate Nine or the Sink?", "grade_at_least 5"),
            line("greeting", "Long Shift's open every hour a tram runs. That's every hour."),
        ], [bark("Dispatcher held me at the Rim for nine minutes. No reason given. There's never a reason."),
            bark("Ration count's off again. Off by the same amount as last week.")]),
    "row-choir-listener": talker(
        "row-choir-listener", "Choir listener", "choir", "Quarter Tone regular", [
            line("cantor", "You hear it too, don't you. Sit. The music's kept low so we can.", "archetype cantor"),
            line("member", "Nine listened first. We keep the volume down out of respect.", "member_of choir"),
            line("enemy", "Halvard drinks two doors up. We don't mind. They mind.", "enemy_of_me"),
            line("greeting", "Keep your voice down, please. Not for us."),
        ], [bark("There. Under the bass. Did you hear it?"),
            bark("Solenne says we buy more than Sable does. That's not a sin. It's a ledger.")]),
    "row-clause-regular": talker(
        "row-clause-regular", "Clause regular", None, "The Clause", [
            line("legal", "Day zero. Nobody here owns your lease. Chalk a line for somebody who hasn't made it.", "legal"),
            line("wake", "Day what? Chalk it. We all chalk it. Next round's on whoever's closest to ninety.", "is_wake"),
            line("veteran", "Grade five and still drinking with us. Most of them move up the street.", "grade_at_least 5"),
            line("greeting", "The Clause doesn't care who decanted you. It cares who's buying."),
        ], [bark("Somebody's tally stopped at sixty-one. Nobody rubs it out."),
            bark("Stray's no insult on the Row. Say it two streets over and see.")]),
    "row-unmoored-runner": talker(
        "row-unmoored-runner", "Unmoored runner", "unmoored", "Spare Parts regular", [
            line("member", "Terminal's behind the counter. Trace down here is Sable's, so jack light.", "member_of unmoored"),
            line("enemy", "Truce holds. Doesn't mean we talk.", "enemy_of_me"),
            line("ghost", "Ghost template. You'll want the House Lights core one night. Everybody does once.", "archetype ghost"),
            line("greeting", "Spare Parts. Everything in here used to be something else. Us too."),
        ], [bark("Thirty seconds of dark. You'd be amazed what thirty seconds is worth on this street.")]),
    "row-card-player": talker(
        "row-card-player", "Card player", "sable", "Sable's card court", [
            line("marked", "You drew on the Row. We saw. Everybody saw. Run, or sit very still.", "marked"),
            line("curfew", "Curfew. The Stair's shut. House rule: nobody leaves the table till the Wardens open it.", "event_active curfew"),
            line("surge", "The Choir lot are all smiling. Means the Lattice is strange tonight. Don't play a Cantor.", "event_active choir-surge"),
            line("member", "Deal you in? You know the house rules. You wrote half of them.", "member_of sable"),
            line("enemy", "We don't bite on the Row. That's the arrangement. Don't ask whose.", "enemy_of_me"),
            line("greeting", "Cards are Sable's. So's the peace. Pull up a crate."),
        ], [bark("Somebody sold a Halvard pass for two hundred. Expired, of course."),
            bark("Nobody draws on the Row. Somebody always thinks they're the exception.")]),
}

# Fixed-cast additions on the demo branch (lines from personae, plus new
# lines from #143 section 6). Their existing records are kept and extended.
DOLF_LINES = [
    line("marked", "You know what you did out there. Drink slow. Sable's outside.", "marked"),
    line("situation", "Hardline template. Same as some of you. Chose the bar. You can choose too.", "first_meeting", "archetype hardline"),
    line("first", "Vesper's at the end. Drink first. It's a rule; it's her rule.", "first_meeting"),
    line("veteran", "You can be shot on the Row now. Notice how nobody does.", "grade_at_least 5"),
    line("returned", "Good. You came back. Most don't, the first week.", "completed_contract vesper-first-thing"),
    line("greeting", "Row's neutral. I'm the reason it stays that way when Sable's not looking."),
]
DOLF_BARKS = [bark("Hardline template. Hands this size, and all they do is pour.")]

SOLENNE_LINES = [
    line("marked", "Red name at my counter. Cash only, sweetheart, and quick.", "marked"),
    line("cantor", "Cantor. Your tab's open. You lot crash hardest and tip best.", "archetype cantor"),
    line("first", "Pink for the shakes, blue for the jack-in, nothing for the crash. The crash is the price.", "first_meeting"),
    line("greeting", "Choir buys more than Sable does. Don't tell Reyes; he'd raise the rent."),
]
SOLENNE_BARKS = [bark("Three in a day and you're mine for a week. Business model, sweetheart.")]

# --- Drinks and counters --------------------------------------------------
# Canon wants "a small shock reduction"; the purchase path does not floor
# shock at zero yet (commerce.py:303), so demo drinks restore stamina instead.

DRINKS = [
    ("con_row_amber", "Upstairs Amber", 30, "stamina +15", 15),
    ("con_row_shift", "Long Shift Lager", 8, "stamina +10", 10),
    ("con_row_low_note", "Low Note", 15, "stamina +10", 10),
    ("con_row_tally", "The Tally", 5, "stamina +5", 5),
    ("con_row_coolant", "Coolant", 12, "stamina +10", 10),
]

BARS = [  # vendor id, name, faction, counter object, drink, region (x, y, w, h)
    ("row-upstairs", "Upstairs", "halvard", "row-bar-1", "con_row_amber"),
    ("row-long-shift", "The Long Shift", "kestrel", "row-bar-2", "con_row_shift"),
    ("row-quarter-tone", "The Quarter Tone", "choir", "row-bar-3", "con_row_low_note"),
    ("row-clause", "The Clause", None, "row-bar-4", "con_row_tally"),
    ("row-spare-parts", "Spare Parts", "unmoored", "row-bar-5", "con_row_coolant"),
]

# --- NPC templates ---------------------------------------------------------

def template(tid: str, name: str, faction, dialogue: str, kind: str = "wander", **extra) -> dict:
    params = {"anchor": True} if kind == "talker" else {}
    rec = {"id": tid, "name": name, "faction": faction, "grade": 1, "attributes": ATTRS,
           "behaviours": [{"kind": kind, "params": params}], "xp": 0,
           "dialogue": dialogue, "loot": [{"item": "con_kestrel_ration", "chance": 1, "count": 1}]}
    rec.update(extra)
    return rec


TEMPLATES = [
    template("npc-row-halvard-offduty", "Halvard staff", "halvard", "row-halvard-offduty"),
    template("npc-row-sablier-offduty", "Sablier staff", "sablier", "row-sablier-offduty"),
    template("npc-row-kestrel-crew", "Kestrel crew", "kestrel", "row-kestrel-crew"),
    template("npc-row-choir-listener", "Choir listener", "choir", "row-choir-listener"),
    template("npc-row-clause-regular", "Clause regular", None, "row-clause-regular"),
    template("npc-row-unmoored-runner", "Unmoored runner", "unmoored", "row-unmoored-runner"),
    template("npc-row-card-player", "Card player", "sable", "row-card-player", "talker"),
    template("npc-row-solenne", "Mira Solenne", "sable", "solenne", "talker"),
    template("npc-halo-dolf", "Dolf", None, "dolf", "talker"),
]


def spawner(sid: str, npc: str, count: int, x: int, y: int, w: int, h: int) -> dict:
    return {"id": sid, "npc": npc, "count": count, "respawn_seconds": RESPAWN,
            "condition": "always", "region": {"x": x, "y": y, "w": w, "h": h}}


# Regions from the frozen map (b7a2b68): bar interiors north of row 8.
ROW_SPAWNERS = [
    spawner("sable-enforcer-stair", "npc-sable-enforcer", 1, 8, 11, 1, 3),
    spawner("sable-enforcer-strip", "npc-sable-enforcer", 1, 45, 9, 2, 1),
    spawner("upstairs-halvard", "npc-row-halvard-offduty", 1, 8, 5, 11, 3),
    spawner("upstairs-sablier", "npc-row-sablier-offduty", 1, 8, 5, 11, 3),
    spawner("long-shift-crew", "npc-row-kestrel-crew", 2, 25, 2, 11, 5),
    spawner("quarter-tone-listeners", "npc-row-choir-listener", 2, 39, 2, 13, 5),
    spawner("clause-regulars", "npc-row-clause-regular", 2, 55, 4, 5, 3),
    spawner("spare-parts-runners", "npc-row-unmoored-runner", 2, 71, 3, 12, 4),
    spawner("card-court-players", "npc-row-card-player", 2, 49, 18, 7, 1),
    spawner("card-court-solenne", "npc-row-solenne", 1, 59, 20, 1, 1),
    spawner("plainclothes-warden", "npc-plainclothes-warden", 1, 10, 9, 70, 8),
]

# The Halo: Vesper and the bouncer as drawn; Dolf behind the bar (row 6);
# three regulars from three different crowds instead of four Sable members.
HALO_SPAWNERS = [
    spawner("halo-bouncer", "npc-halo-bouncer", 1, 9, 9, 1, 1),
    spawner("vendor-sodium-tin-halo-vesper", "npc-vendor-sodium-tin-halo-vesper", 1, 33, 9, 1, 3),
    spawner("halo-dolf", "npc-halo-dolf", 1, 16, 6, 14, 1),
    spawner("halo-regular-crew", "npc-row-kestrel-crew", 1, 12, 10, 18, 3),
    spawner("halo-regular-stray", "npc-row-clause-regular", 1, 12, 10, 18, 3),
    spawner("halo-regular-runner", "npc-row-unmoored-runner", 1, 12, 10, 18, 3),
]


def main() -> None:
    for did, rec in DIALOGUE.items():
        save(f"dialogue/{did}.json", rec)
    for did, lines, barks in (("dolf", DOLF_LINES, DOLF_BARKS), ("solenne", SOLENNE_LINES, SOLENNE_BARKS)):
        rec = load(f"dialogue/{did}.json")
        rec["lines"], rec["barks"] = lines, barks
        save(f"dialogue/{did}.json", rec)
    vesper = load("dialogue/vesper.json")
    for offer in vesper["offers"]:
        if offer["kind"] == "contract":
            offer["when"] = ["not_marked"]  # #143 section 5: drawing costs the Row's work
    save("dialogue/vesper.json", vesper)

    items = load("items.json")
    keep = [i for i in items["items"] if not i["id"].startswith("con_row_")]
    for iid, name, price, desc, stamina in DRINKS:
        keep.append({"id": iid, "name": name, "class": "consumable", "tier": 1, "weight": 0.0,
                     "base_price": price, "description": desc,
                     "consumable": {"effects": {"stamina": stamina}, "cooldown_class": "food"},
                     "quality": {"kind": "none", "key": ""}})
    items["items"] = keep
    save("items.json", items)

    vendors = load("vendors.json")
    ids = {b[0] for b in BARS}
    vendors["vendors"] = [v for v in vendors["vendors"] if v["id"] not in ids]
    for vid, name, faction, obj, drink in BARS:
        vendors["vendors"].append({"id": vid, "name": name, "tier": "list",
                                   "stock": [{"item": drink}, {"item": "con_kestrel_ration"}],
                                   "faction": faction, "zone": "sodium-row", "object_id": obj})
    save("vendors.json", vendors)

    npcs = load("npcs.json")
    tids = {t["id"] for t in TEMPLATES}
    npcs["npcs"] = [n for n in npcs["npcs"] if n["id"] not in tids] + TEMPLATES
    save("npcs.json", npcs)

    row = load("zones/sodium-row.json")
    names = {b[3]: b[1] for b in BARS}
    vids = {b[3]: b[0] for b in BARS}
    for obj in row["objects"]:
        if obj["id"] in names:
            obj["params"]["name"] = names[obj["id"]]
            obj["params"]["vendor"] = vids[obj["id"]]
    row["spawners"] = ROW_SPAWNERS
    save("zones/sodium-row.json", row)

    halo = load("zones/sodium-tin-halo.json")
    halo["spawners"] = HALO_SPAWNERS
    save("zones/sodium-tin-halo.json", halo)

    # Speech for the Row's cast (#143 section 9, item 3): release Vesper, Dolf
    # and Solenne from the dormant S27 bundle on this branch, and bind Vesper's
    # counter template to her talker record. The technical lead's demo switch
    # may move this behind DOOR_BLACKSITE_DEMO.
    bundle = load("bundles/s27-cast.json")
    bundle["members"]["dialogue"] = [d for d in bundle["members"]["dialogue"]
                                     if d not in ("vesper", "dolf", "solenne")]
    save("bundles/s27-cast.json", bundle)
    npcs = load("npcs.json")
    for n in npcs["npcs"]:
        if n["id"] == "npc-vendor-sodium-tin-halo-vesper":
            n["dialogue"] = "vesper"
    save("npcs.json", npcs)


if __name__ == "__main__":
    main()
