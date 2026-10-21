"""Author S10's canonical data; not imported by the game service."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "src/blacksite/content"


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def main() -> None:
    definitions = [
        ("hymn_steady","Steady","hymn",1,.5,12,{"shock":-20},"You settle your breathing. Shock falls by twenty."),
        ("hymn_mend","Mend","hymn",1,1,15,{"heal":3,"seconds":5},"You hold the note. Health returns over five seconds."),
        ("hymn_march","March","hymn",2,1,30,{"stamina_multiplier":.5,"seconds":10},"You keep time. Sprinting costs half the stamina."),
        ("hymn_ward","Ward","hymn",2,1.5,40,{"armour":5,"seconds":12},"You brace. Every armour type gains five."),
        ("hymn_ninefold","Ninefold","hymn",3,2,90,{"revive":1},"You pick up one downed crew member within hymn range."),
        ("dis_jam","Nerve-jam","dissonance",1,.5,8,{"weapon_multiplier":1.5,"seconds":4},"You break the rhythm. The target's weapon takes longer to recover."),
        ("dis_stutter","Stutter","dissonance",1,.5,10,{"move_ticks":4,"seconds":4},"You catch a step. The target moves at four ticks per tile."),
        ("dis_shear","Shear","dissonance",2,1,14,{"damage":25,"shock":20},"You pull the note apart. The target takes dissonance and shock."),
        ("dis_hush","Hush","dissonance",2,1,20,{"hush":1,"seconds":6},"You close the note. The target cannot use consumables or hymns."),
        ("dis_choir","Choir","dissonance",3,2,60,{"damage":30,"shock":30,"area":4},"You release the chord. Hostile bodies within four tiles take dissonance."),
    ]
    hymns = [{"id":aid,"name":name,"kind":kind,"tier":tier,"cast_seconds":cast,
        "cooldown_seconds":cooldown,"effect":effect,"description":description,
        "requires_one_of":[] if tier==1 else ["imp_res_chord","imp_res_ninefold_lattice"] if tier==2 else ["imp_res_ninefold_lattice"]}
        for aid,name,kind,tier,cast,cooldown,effect,description in definitions]
    write(CONTENT/"hymns.json",{"schema":1,"hymns":hymns})
    write(CONTENT/"npcs.json",{"schema":1,"npcs":[{"id":"npc-wake-drone","name":"Training drone",
        "grade":1,"attributes":{"frame":1,"nerve":1,"cortex":1,"resonance":1,"vitals":1},
        "health":20,"training":True,"attack":{"damage":5,"cooldown":1.5,"accuracy":75,"damage_type":"kinetic","range":6}}]})
    starts = json.loads((CONTENT/"starts.json").read_text(encoding="utf-8"))
    for start in starts["starts"]:
        start["recovery_items"] = {"wpn_kestrel_sidearm":1,"ammo_9x":50,"arm_wake_coverall":1,"con_sablier_patch":2}
        start["equipment"].update(weapon_side="wpn_kestrel_sidearm",melee="wpn_kestrel_baton",quick1="con_sablier_patch")
    write(CONTENT/"starts.json",starts)
    zone = json.loads((CONTENT/"zones/vatside-wake-hall.json").read_text(encoding="utf-8"))
    next(o for o in zone["objects"] if o["id"]=="corridor-door")["params"]["training_npc"] = "npc-wake-drone"
    next(o for o in zone["objects"] if o["id"]=="corridor-door")["params"]["training_tile"] = [23,14]
    write(CONTENT/"zones/vatside-wake-hall.json",zone)
    items = json.loads((CONTENT/"items.json").read_text(encoding="utf-8"))
    for item in items["items"]:
        if item["id"]=="arm_wake_coverall": item["secured_default"] = True
        if item.get("weapon",{}).get("melee"):
            item["weapon"].update(cooldown=1.0,accuracy=75)
    write(CONTENT/"items.json",items)
    keymaps = json.loads((CONTENT/"keymaps.json").read_text(encoding="utf-8"))
    keymaps["actions"].update({"abilities":{"context":"zone","label":"abilities"},
        "weapon_cycle":{"context":"zone","label":"switch equipped weapon"},
        "stealth":{"context":"zone","label":"toggle stealth"}})
    for keymap in keymaps["keymaps"]:
        keymap["bindings"].update(abilities=["v","V"],weapon_cycle=["x","X"],stealth=["z","Z"])
    write(CONTENT/"keymaps.json",keymaps)


if __name__ == "__main__":
    main()
