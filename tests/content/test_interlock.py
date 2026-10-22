"""Entity 1.4/5 and game 6.4: commissioned machines bind real targets."""

from tests.content.support import World, find


def test_interlock_fixture_loads_with_turret_light_door_and_hardware(world: World):
    tree = world.load()
    assert not world.problems()
    objects = {obj.kind for obj in tree.zones["fx-street"].meta.objects}
    assert {"door", "turret", "light", "hardware"} <= objects


def test_interlock_rejects_unbound_powered_actor(world: World):
    world.edit("zones/fx-street.json", lambda data: find(data["objects"], "fx-street-turret")["params"].update(spawners=["missing"]))
    assert any("local spawner bindings" in message for message in world.messages())


def test_interlock_rejects_owned_service_persistence(world: World):
    def change(data):
        control = data["rooms"][2]["controls"][2]
        control.update(scope="mission", permission="contract", owner_policy=True)
    world.edit("cores/fx-core-a.json", change)
    assert any("service effects cannot persist" in message for message in world.messages())
