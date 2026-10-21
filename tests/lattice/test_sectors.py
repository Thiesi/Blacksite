"""Game design 6.1: discoverable cells and explicit access credentials."""

from dataclasses import replace

from blacksite.content.schema import Cell, Sector, Uplink
from blacksite.server.lattice.sectors import Credentials, Sectors, permitted, requirement_label


def test_design_6_1_hidden_descent_is_not_disclosed() -> None:
    entrance=Cell("entry","public",(0,0),("drain",),"Entrance")
    drain=Cell("drain","descent",(1,0),("entry",),"Drain",access="hidden")
    sectors=Sectors([Sector("vatside","Vatside",(entrance,drain),entry="entry")])
    assert [c.id for c in sectors.known("vatside",set())]==["entry"]
    assert [c.id for c in sectors.known("vatside",{"drain"})]==["entry","drain"]
    assert sectors.entrance("vatside")=="entry"


def test_design_6_1_gates_require_real_inventory_or_rig_credentials() -> None:
    credentials=Credentials(items=frozenset({"key_gate"}),programs=frozenset({"prg_skeleton"}),
        program_tiers=(("key",2),),faction="wardens",standing=(("wardens",30),))
    for requirement in ("item:key_gate","prg_skeleton","program:prg_skeleton","program:key:2","faction:wardens","standing:wardens:30"):
        assert permitted(requirement,credentials)
        assert not permitted(requirement,Credentials())
    assert not permitted("program:key:3",credentials)
    assert not permitted("event:ring-fall",credentials)
    assert permitted("event:ring-fall",replace(credentials,events=frozenset({"ring-fall"})))
    assert requirement_label("program:key:2")=="key program tier 2"


def test_design_6_1_uplink_is_an_explicit_adjacent_destination() -> None:
    a=Cell("a","public",(0,0),(),"Core uplink",uplink=Uplink("vatside","b"))
    b=Cell("b","public",(0,0),(),"Vatside uplink",uplink=Uplink("core","a"))
    registry=Sectors([Sector("core","Core",(a,)),Sector("vatside","Vatside",(b,))])
    assert registry.adjacent("core","a","vatside","b")
    assert not registry.adjacent("core","a","vatside","other")
