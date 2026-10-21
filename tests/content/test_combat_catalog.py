"""S10 content from game design 4/5.3/17.1 and canonical ID rules."""

from pathlib import Path
import re

from blacksite.content.loader import load_content
from blacksite.content.validate import validate


def test_hymns_and_private_training_match_canonical_schedule(repo_root: Path) -> None:
    tree=load_content(repo_root/"src/blacksite/content")
    assert validate(tree)==[]
    source=(repo_root/"docs/design/00-game-design.md").read_text(encoding="utf-8")
    rows=re.findall(r"^\| `(hymn_\w+|dis_\w+)` \| ([^|]+) \| (hymn|dissonance) \| (\d) \| ([\d.]+) s \| ([\d.]+) s \|",source,re.M)
    assert len(rows)==10 and len(tree.hymns)==10
    for aid,name,kind,tier,cast,cd in rows:
        ability=tree.hymns[aid]
        assert (ability.name,ability.kind,ability.tier,ability.cast_seconds,ability.cooldown_seconds)==(name.strip(),kind,int(tier),float(cast),float(cd))
    npc=tree.npcs["npc-wake-drone"]
    assert npc.training and npc.health==20 and npc.attack.damage==5 and npc.attack.cooldown==1.5
    for item in tree.items.values():
        if item.weapon and item.weapon.melee: assert item.weapon.cooldown==1 and item.weapon.accuracy==75


def test_training_anchor_cannot_spawn_in_a_wall(repo_root: Path) -> None:
    tree=load_content(repo_root/"src/blacksite/content")
    obj=next(o for o in tree.zones["vatside-wake-hall"].meta.objects if o.params.get("training_npc"))
    obj.params["training_tile"]=[0,0]
    assert any("training tile" in str(p) for p in validate(tree))
