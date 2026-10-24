"""Game 12: Surge changes magnitudes and compatible stats, not clocks."""

from dataclasses import replace

import pytest

from blacksite.content.schema import IceTemplate
from blacksite.server.event_effects import beneficial, compatible, swap
from blacksite.server.lattice.ice import Activation, Ice


def test_game_12_benefits_preserve_damage_range_duration_and_restrictions() -> None:
    effect = {'heal': 3, 'armour': 5, 'shock': -20, 'stamina': 10,
              'stamina_multiplier': .5, 'seconds': 12, 'area': 6, 'damage': 20,
              'revive': 1, 'requires': 'down'}
    value = beneficial(effect, 1.3)
    assert value['heal'] == pytest.approx(3.9) and value['armour'] == 6.5
    assert value['shock'] == -26 and value['stamina'] == 13
    assert abs(value['stamina_multiplier']-.35) < 1e-10
    assert {k: value[k] for k in ('seconds', 'area', 'damage', 'revive', 'requires')} == {
        k: effect[k] for k in ('seconds', 'area', 'damage', 'revive', 'requires')}
    assert effect['heal'] == 3 and effect['stamina_multiplier'] == .5
    assert beneficial({'damage': 10, 'shock': 20}, 1.3) == {'damage': 10, 'shock': 20}


def test_game_12_ice_compatibility_preserves_role_and_counterplay() -> None:
    base = IceTemplate('base', 'Base', 'tripwire', variants=('pulse',), tier=2)
    pulse = replace(base, id='pulse', tier=1)
    assert compatible(base, pulse)
    for invalid in (replace(pulse, black=True), replace(pulse, tier=3),
                    replace(pulse, class_='turnstile'), replace(pulse, trigger='touch'),
                    replace(pulse, behaviour='hunter'), replace(pulse, role='gate'),
                    replace(pulse, id='unannounced')):
        assert not compatible(base, invalid)
    assert not compatible(replace(base, black=True), pulse)


def test_game_12_swap_preserves_received_damage_activations_and_clocks() -> None:
    base = IceTemplate('base', 'Base', 'tripwire', integrity=50, attack=10, variants=('pulse',))
    variant = replace(base, id='pulse', integrity=40, attack=8)
    ice = Ice.spawn('ice', base, ('instance', 'room'), 1, 0)
    ice.integrity = 30
    activation = Activation(1, 51, 80, 100)
    ice.activations['runner'] = activation
    ice.next_attack, ice.next_move, ice.phase_origin, ice.phase = 84, 94, 12, 'casting'
    ice.shots, ice.gate_until_utc = 2, 600
    swap(ice, variant, 1, 60)
    assert ice.integrity == 20 and ice.maximum == 40 and ice.attack == 8
    assert ice.activations['runner'] is activation
    assert (ice.next_attack, ice.next_move, ice.phase_origin, ice.phase) == (84, 94, 12, 'casting')
    assert (ice.shots, ice.gate_until_utc) == (2, 600)
    swap(ice, base, 1, 100)
    assert ice.integrity == 30 and ice.maximum == 50


def test_game_12_ending_surge_never_resurrects_defeated_ice() -> None:
    base = IceTemplate('base', 'Base', 'tripwire', integrity=50, variants=('pulse',))
    pulse = replace(base, id='pulse', integrity=30)
    ice = Ice.spawn('ice', pulse, ('instance', 'room'), 1, 0)
    ice.integrity = 0
    swap(ice, base, 1, 100)
    assert ice.integrity == 0 and not ice.alive
