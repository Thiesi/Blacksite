"""Game 7.7: canonical schedule and honest phase-aware activation."""

from pathlib import Path

from blacksite.content.loader import load_content
from blacksite.content.validate import validate


def test_game_7_7_exact_sixteen_relay_schedule_and_sources():
    tree=load_content(Path(__file__).parents[1]/'src/blacksite/content')
    expected={
        'shaft':('spire-shaft-head',5,20,'shaft_telemetry',0),
        'cold-chain':('vatside-clinics',2,10,'surgery_fee',.9),
        'depot':('tramyard-depots',2,10,'vendor_refresh',1800),
        'gate-nine':('tramyard-wall-gate',3,10,'fast_gate',0),
        'cable':('sink-rim',3,10,'cable_ride',0),
        'sump':('sink-floor',2,10,'pump_telemetry',0),
        'bell':('chapel-towers',3,10,'hymn_radius',1),
        'zero':('oldworks-main',3,10,'trace_gain',.9),
        'yard':('oldworks-yards',3,10,'fabrication_quality',.05),
        'block':('terraces-blocks',2,10,'rent_and_ice',.9),
        'cavern':('under-caverns',3,10,'patrol_overlay',0),
        'outworks':('under-outworks',4,10,'depth_contribution',1.1),
        'mile':('scour-ring-1',2,30,'convoy_patrol',0),
        'beacon':('scour-ring-2',3,30,'impact_forecast',300),
        'crash':('scour-ring-3',4,30,'salvage_grade',1),
        'far':('scour-ring-4',4,30,'long_range_telemetry',0),
    }
    assert {rid:(r.zone,r.tier,r.rate,r.benefit.kind,r.benefit.amount)
            for rid,r in tree.relays.items()}==expected
    for rid,relay in tree.relays.items():
        assert relay.core=='lat-relay-'+rid
        assert tree.cores[relay.core].owner_kind=='relay'
        assert tree.vendors[relay.vendor].relay==rid
    assert {rid for rid,r in tree.relays.items() if r.requires_level}=={'shaft'}


def test_game_7_7_all_commissioned_relays_resolve_to_actual_sources():
    tree=load_content(Path(__file__).parents[1]/'src/blacksite/content')
    assert not validate(tree)
    assert {rid for rid in tree.relays if tree.active('relays',rid)} == set(tree.relays)
    for rid,relay in tree.relays.items():
        if tree.active('relays',rid):
            assert relay.zone in tree.zones and tree.active('cores',relay.core)
            assert any(o.id==relay.terminal and o.kind=='relay' and o.params['relay']==rid
                       for o in tree.zones[relay.zone].meta.objects)
        else:
            assert not tree.active('cores',relay.core)
            assert not tree.active('vendors',relay.vendor)
    assert not any(relay.zone.startswith('sodium-') for relay in tree.relays.values())
