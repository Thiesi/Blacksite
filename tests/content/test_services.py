"""Entity 2.13: commissioned services bind real, fixed work orders."""

from tests.content.support import World


def test_game_7_5_service_links_repeatable_fixed_contract_and_effect_audiences(world: World) -> None:
    contracts = world.read('contracts.json')
    job = contracts['contracts'][0]
    job.update(service=True, story=False, crew_scaling=False, faction='fx-alpha',
               reward={'chits': [200, 200], 'xp': 100, 'standing': {'fx-alpha': 5}})
    world.write('contracts.json', contracts)
    services = world.read('services.json')
    service = services['services'][0]
    service['contract'] = job['id']
    service['fault_effects'] = [{'type': 'reveal', 'zone': 'fx-street', 'params': {'what': 'fault'}}]
    service['allocations'][1]['effects'][0]['audience'] = 'workers'
    world.write('services.json', services)
    assert not world.problems()
    assert world.load().services['fx-pump'].allocations[1].effects[0].audience == 'workers'
    job['story'] = True
    world.write('contracts.json', contracts)
    assert any('repeatable' in message for message in world.messages())


def test_game_7_5_missing_work_order_reference_is_rejected(world: World) -> None:
    services = world.read('services.json')
    services['services'][0]['contract'] = 'missing'
    world.write('services.json', services)
    assert any("contract 'missing'" in message for message in world.messages())


def test_game_7_5_active_price_effect_cannot_silently_bind_a_missing_counter(world: World) -> None:
    services = world.read('services.json')
    service = services['services'][0]
    service['allocations'][0]['effects'] = [{'type':'price_modifier','zone':'fx-street',
        'params':{'service':'buyback_budget','multiplier':2,'vendor':'missing-vendor','object':'missing-counter'}}]
    world.write('services.json',services)
    messages = world.messages()
    assert any("vendor 'missing-vendor'" in message for message in messages)
    assert any('resolved zone/object' in message for message in messages)
