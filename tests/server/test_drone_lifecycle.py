"""Game 5.3: background tool saves cannot resurrect a deleted character."""

from blacksite.server.app import Server
from blacksite.server.storage.db import Storage
from tests.server.test_drone_ownership import operator
from tests.server.test_substances import give


def test_entity_2_2_delete_wins_over_pending_drone_and_periodic_save(operator,tmp_path):
    game,a,b,player,engine = operator
    iid = give(game,a,"drn_kestrel_mule")
    engine.command(player,iid,"deploy"); game.commit_commerce()
    store = Storage(tmp_path/"deletion.db",game.clock)
    try:
        # Match the headless world's stable authority, using the storage API.
        store.mark_dirty("meta","origin",game.core.sessions.origin)
        for resident in game.core.characters.players.values():
            store.mark_dirty("players",resident.id,resident.record())
            store.mark_dirty("identities",resident.bbs_user_id,game.core.characters.identities[resident.bbs_user_id])
        for key,item in game.core.commerce.items.items():
            store.mark_dirty("items",key,item.record())
        store.flush_now()
        characters = game.core.characters
        characters.outbox.clear()
        engine.command(player,iid,"hold")  # A transfer already awaits the I/O writer.
        characters.deleting.add(player.id)
        characters.queue("delete",player.bbs_user_id,player,token=a.session.id)
        game.clock.advance(50-game.clock.now_tick()%50)
        engine.tick(game.clock.now_tick())  # The same tick reaches a periodic-save boundary.
        server = Server(tmp_path,clock=game.clock)
        server.core,server.storage = game.core,store
        server._character_writes()  # Production ordering: character deletes, then commerce.
        store.flush_now()
        assert player.id not in characters.players
        assert all(row["id"] != player.id for row in store.character_state()["players"])
        assert iid not in game.core.commerce.items
        assert store.db.execute("SELECT 1 FROM items WHERE id=?",(iid,)).fetchone() is None
        characters.queue("save",player.bbs_user_id,player,immediate=True)  # A late old callback.
        assert not characters.outbox
        engine.tick(game.clock.now_tick())
        assert iid not in engine.actors
    finally:
        store.close()
