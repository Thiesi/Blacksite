"""S19 exact core-data references cannot activate with a dangling record."""

from tests.content.support import World


def test_entity_1_10_checks_the_named_mission_data_in_its_actual_room(world: World) -> None:
    tree = world.load()
    core = tree.cores['fx-core-a']
    room = next(room for room in core.rooms if room.data)
    data = world.read('contracts.json')
    stage = data['contracts'][0]['stages'][1]
    stage.update(input='lift', completion='lifted', target={
        'kind': 'core_room', 'core': core.id, 'room': room.id, 'data': room.data[0].id})
    world.write('contracts.json', data)
    assert not world.problems()
    stage['target']['data'] = 'missing-mission-record'
    world.write('contracts.json', data)
    assert any("data 'missing-mission-record' does not exist" in message for message in world.messages())
