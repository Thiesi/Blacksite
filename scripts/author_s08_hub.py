"""Reproduce the authored S08 grids/sidecars from gazetteer sketches.

Run from the repository root. No game or player state is read.
"""

import json
from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "src/blacksite/content"


def dump(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build() -> None:
    # Object IDs below are the binding names for future consuming slices.
    specs = [
        ("core-plaza", "Meridian Plaza", "The Core", "safe", 90, 40, 12,
         [("kestrel-bank", 9, 5, "bank"), ("plaza-general-vendor", 76, 5, "vendor"),
          ("warden-recruiter", 17, 30, "vendor"), ("civic-notice-board", 69, 30, "terminal"),
          ("civic-descent", 72, 30, "descent_console"),
          ("plaza-light-west",36,13,"light"),("plaza-light-east",54,13,"light"),
          *[(f"plaza-public-{i}", x, y, "terminal") for i, (x, y) in enumerate([(31,5),(57,5),(9,30),(80,30)],1)]]),
        ("core-tram-hub", "Central Tram Hub", "The Core", "safe", 80, 30, 12,
         [("kestrel-ticket-office", 8,4,"vendor"), ("kestrel-recruiter",38,4,"vendor"),
          ("hub-noodle-counter",68,4,"vendor"), ("hub-public-west",23,4,"terminal"), ("hub-public-east",53,4,"terminal")]),
        ("core-precinct", "Warden Precinct", "The Core", "safe", 50, 24, 12,
         [("warden-quartermaster",5,3,"vendor"),("warden-contract-handler",27,3,"vendor"),
          ("marshal-office",40,16,"door"),("bounty-desk",42,19,"terminal"),
          ("precinct-member-terminal",39,3,"terminal"),("precinct-vault-hardware",44,3,"hardware"),
          ("warden-faction-vat",34,19,"vat"),("holding-cell-west",8,13,"door"),("holding-cell-east",31,13,"door")]),
        ("vatside-vat-row", "Vat Row", "Vatside", "contested", 90,36,9,
         [("black-clinic",76,25,"vendor"),("vat-technicians",44,28,"vendor"),
          ("sablier-faction-vat",15,15,"vat"),("vatline-hardware",79,13,"hardware")]),
        ("sodium-row", "Sodium Row", "Sodium Row", "contested",100,30,13,
         [("row-drug-dealer",48,20,"vendor"),("row-ticket-tout",64,20,"vendor"),
          ("row-stage",30,7,"light"),("row-card-table",38,20,"light"),
          *[(f"row-bar-{i}",x,7,"vendor") for i,x in enumerate((8,18,50,63,75),1)],
          *[(f"row-public-{i}",x,15,"terminal") for i,x in enumerate((19,50,80),1)]]),
        ("sodium-tin-halo", "The Tin Halo", "Sodium Row", "pocket",44,22,8,
         [("vesper",8,15,"vendor"),("halo-bar",16,15,"vendor"),("halo-back-room",31,18,"door"),
          ("ferrymen-liaison",34,15,"vendor"),("halo-contract-board",38,3,"terminal"),("halo-market-board",37,16,"terminal")]),
        ("terraces-blocks", "Block Street", "The Terraces", "contested",120,40,11,
         [("letting-office",103,10,"vendor"),("corner-grocer",96,29,"vendor"),
          ("warden-outpost",108,30,"door"),("block-relay",57,29,"relay"),
          ("block-relay-hardware",60,29,"hardware"),
          *[(f"blocks-public-{i}",x,y,"terminal") for i,(x,y) in enumerate(((105,21),(105,29),(92,34)),1)]]),
        ("terraces-lobby", "Residence Lobby", "The Terraces", "pocket",40,24,10,
         [("lobby-concierge",13,4,"vendor"),("lobby-lift",13,8,"door"),
          ("lobby-public-terminal",28,12,"terminal"),("lobby-mailboxes",10,15,"light"),
          *[(f"apartment-door-{i}",x,19,"apartment_door") for i,x in enumerate((6,12,18,24,30),1)]]),
    ]
    zones: dict[str, dict] = {}
    grids: dict[str, list[list[str]]] = {}
    for zid,name,district,safety,w,h,sight,objects in specs:
        grids[zid] = [["#" if x in (0,w-1) or y in (0,h-1) else "." for x in range(w)] for y in range(h)]
        zones[zid] = dict(schema=1,id=zid,name=name,district=district,safety=safety,sight_radius=sight,
                          spawn=[3,3],exits=[],objects=[],pockets=[],lore=["zone-"+zid])
        for oid,x,y,kind in objects:
            zones[zid]["objects"].append(dict(id=oid,tile=[x,y],kind=kind,
                essential=kind in ("bank","vat") or "public" in oid,
                params=dict(name=oid.replace("-"," ").capitalize(), **({"open":True} if kind=="door" else {}))))
    for zid in ("vatside-wake-hall","vatside-clinics"):
        zones[zid] = json.loads((CONTENT/"zones"/(zid+".json")).read_text(encoding="utf-8"))
        zones[zid]["lean"] = None  # S20 supplies faction records, not this city bundle.
        zones[zid]["exits"] = []
        zones[zid]["objects"] = [o for o in zones[zid]["objects"] if not o["id"].startswith("platform-")
            and o["id"] not in ("cold-chain-hardware","cold-chain-replacement-socket","cold-chain-loan-terminal")]
        zones[zid]["pockets"] = [p for p in zones[zid].get("pockets",[]) if p != dict(x=35,y=20,w=3,h=2)]
        grids[zid] = [list(row) for row in (CONTENT/"zones"/(zid+".map")).read_text(encoding="utf-8").splitlines()]
    def rectangle(zid: str,x:int,y:int,w:int,h:int,char:str) -> None:
        for yy in range(y,y+h):
            for xx in range(x,x+w):
                grids[zid][yy][xx] = char
    # Sketch landmarks: plaza fountain/benches, hub platforms, cells, vat
    # halls, residence blocks and alcoves. Broad perimeter return routes.
    rectangle("core-plaza",40,14,10,9,"~")
    for x in (17,70):
        for y in (10,25): rectangle("core-plaza",x,y,4,2,"%")
    for x in (6,27):
        rectangle("core-precinct",x,9,11,7,"#")
        rectangle("core-precinct",x+1,10,9,5,".")
    for x in (7,33,59):
        rectangle("vatside-vat-row",x,9,20,14,"#")
        rectangle("vatside-vat-row",x+1,10,18,12,"V")
        grids["vatside-vat-row"][22][x+10] = "+"
    for i,x in enumerate((8,27,46,65,84),1):
        rectangle("terraces-blocks",x,10,13,15,"#")
        rectangle("terraces-blocks",x+1,11,11,13,".")
        zones["terraces-blocks"]["objects"].append(dict(id=f"block-door-{i}",tile=[x+9,24],kind="door",params={"open":True}))
    for x in (8,32): rectangle("sodium-tin-halo",x,7,3,2,"%")
    for x in (9,39,70): rectangle("sodium-row",x,11,4,2,"%")
    # Exits land one tile inward from their reciprocal exit. This prevents
    # street bounce while keeping return routes legible.
    links = [
        ("vatside-wake-hall",(38,16),"vatside-clinics",(2,2),"door"),
        ("vatside-clinics",(77,2),"core-plaza",(87,2),"street"),
        ("vatside-clinics",(78,30),"vatside-vat-row",(2,2),"street"),
        ("core-plaza",(3,37),"core-tram-hub",(18,27),"street"),
        ("core-plaza",(33,37),"core-precinct",(24,21),"street"),
        ("core-plaza",(62,37),"sodium-row",(2,2),"street"),
        ("core-plaza",(86,37),"terraces-blocks",(45,2),"street"),
        ("vatside-vat-row",(87,2),"terraces-blocks",(79,2),"street"),
        ("core-tram-hub",(24,14),"vatside-clinics",(3,31),"tram"),
        ("core-tram-hub",(39,14),"terraces-blocks",(8,2),"tram"),
        ("sodium-row",(94,26),"sodium-tin-halo",(2,2),"door"),
    ]
    for i,x in enumerate((17,36,55,74,93),1):
        # Multiple shared-lobby entries return to the first public block door.
        zones["terraces-blocks"]["exits"].append(dict(id=f"to-lobby-{i}",tile=[x,24],target_zone="terraces-lobby",target_tile=[3,3],kind="door"))
    zones["terraces-lobby"]["exits"].append(dict(id="to-blocks",tile=[2,2],target_zone="terraces-blocks",target_tile=[17,25],kind="door"))
    for a,at,b,bt,kind in links:
        for origin,ot,target,tt in ((a,at,b,bt),(b,bt,a,at)):
            alias = {"vatside-wake-hall":"wake-hall", "vatside-clinics":"clinics",
                     "vatside-vat-row":"vat-row", "core-tram-hub":"tram-hub"}.get(target,target)
            zones[origin]["exits"].append(dict(id="to-"+alias,tile=list(ot),target_zone=target,
                target_tile=[tt[0],tt[1]+1 if tt[1]+1 < len(grids[target])-1 else tt[1]-1],kind=kind))
    boundaries = [
        ("core-plaza","spire-atrium",(2,2)),
        ("core-tram-hub","tramyard-market",(9,14)),("core-tram-hub","chapel-towers",(54,14)),
        ("core-tram-hub","sink-rim",(69,14)),("vatside-vat-row","under-service",(82,32)),
        ("terraces-blocks","chapel-towers",(116,2)),("sodium-row","oldworks-main",(96,2)),
    ]
    for zid,target,tile in boundaries:
        zones[zid]["objects"].append(dict(id="boundary-"+target,tile=list(tile),kind="door",
            params={"open":True,"unavailable_target":target,"name":"Construction boundary"}))
    # Service work-order anchors from the gazetteer's infrastructure notes.
    for oid,tile,kind in [("cold-chain-hardware",(34,18),"hardware"),
                          ("cold-chain-replacement-socket",(35,20),"hardware"),
                          ("cold-chain-loan-terminal",(36,20),"terminal")]:
        zones["vatside-clinics"]["objects"].append(dict(id=oid,tile=list(tile),kind=kind,params={"name":oid.replace("-"," ")}))
    # Shelter around the repair socket; capture hardware remains contested.
    zones["vatside-clinics"]["pockets"].append(dict(x=35,y=20,w=3,h=2))
    glyph = dict(terminal="T",vendor="$",vat="V",relay="R",hardware="H",bank="$",light="L",
                 door="+",apartment_door="+",tram_stop=">",descent_console="T")
    for zid,meta in zones.items():
        for obj in meta["objects"]:
            x,y = obj["tile"]
            grids[zid][y][x] = glyph[obj["kind"]]
        for ex in meta["exits"]:
            x,y=ex["tile"]
            grids[zid][y][x] = "+" if ex["kind"]=="door" else ">"
            if ex["kind"]=="tram":
                meta["objects"].append(dict(id="platform-"+ex["target_zone"],tile=[x,y],kind="tram_stop",params={"name":"Tram platform"}))
        if zid not in ("vatside-wake-hall","vatside-clinics"):
            # In-game prose follows bible second-person style, based on the
            # gazetteer's atmosphere, without introducing new proper nouns.
            excerpts = {
                "core-plaza":"You cross Meridian Plaza under the Ring. You hear tram bells and the fountain. Wardens watch every corner.",
                "core-tram-hub":"You stand beneath a vaulted roof. You smell hot brakes and noodles. Departure bells ring across five platforms.",
                "core-precinct":"You step onto blue tile under bad lights. You pass holding cells and the Marshal's office. You hear locks turn.",
                "vatside-vat-row":"You pass long halls of amber tanks. You hear a thousand pumps. Behind the third hall, you find a clinic door with no logo.",
                "sodium-row":"You walk under orange lamps on wet pavement. You hear music from six doorways. At the street's end, you see the Tin Halo's half-burnt sign.",
                "sodium-tin-halo":"You step under a halo of tin cans. You see Vesper at the end of the bar, three screens beside a drink. You come here for work.",
                "terraces-blocks":"You pass balconies hung with washing. You see two officers and a drone at the outpost. Between the blocks, you find alleys beyond the lights.",
                "terraces-lobby":"You enter a shared lobby. You pass mailboxes, a concierge and a lift. You look for a door with your name on it.",
            }
            (CONTENT/"text"/("zone-"+zid+".md")).write_text(textwrap.fill(excerpts[zid],width=76)+"\n",encoding="utf-8")
        dump(CONTENT/"zones"/(zid+".json"),meta)
        (CONTENT/"zones"/(zid+".map")).write_text("\n".join("".join(row) for row in grids[zid])+"\n",encoding="utf-8")
    bundle = CONTENT/"bundles/m1-zone-preview.json"
    dump(bundle,dict(schema=1,id="m1-zone-preview",status="active",depends=[],
                     members={"zones":sorted(zones),"text":["zone-"+z for z in sorted(zones)]}))


if __name__ == "__main__":
    build()
