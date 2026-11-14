"""S48c1b: every writer of player or identity state passes the S48 write guards.

Review 6873460059 on #241: guards 1 (Characters.queue never saves or deletes
an unread body) and 2 (Commerce refuses one in ready, propose, settle and
can_commit) hold only while every writer goes through them. This test walks
the server source for every call site (see writer_sites) and fails when a
site appears or disappears without this table changing with it.

A new site is not wrong in itself. Add it here once you have checked how it
treats an unread body, and say why in its reason.
"""

from __future__ import annotations

from tests.characters.writer_sites import writer_sites
from tests.character_helpers import create
from tests.harness import HeadlessServer

G1 = "guard 1: Characters.queue drops save and delete for an unread body"
G2 = "guard 2: Commerce.settle refuses an unread body, and can_commit refuses any effect naming one"
G2_OUTBOX = "commerce outbox: every effect passes Commerce.can_commit before storage (app.Server._character_writes)"

SAVES = {
    "apartments.py::Apartments.__init__.on_attached",
    "apartments.py::Apartments.door",
    "apartments.py::Apartments.enter_visitor",
    "apartments.py::Apartments.move_out",
    "characters.py::Characters.arrive_offline",
    "characters.py::Characters.attach",
    "characters.py::Characters.disconnect",
    "characters.py::Characters.promote",
    "characters.py::Characters.publish",
    "characters.py::Characters.recover",
    "characters.py::Characters.tick",
    "chat.py::Chat.save_settings",
    "combat/engine.py::Combat._mark_player",
    "combat/engine.py::Combat.remember",
    "combat/engine.py::Combat.tick",
    "drones.py::Drones.tick",
    "faction_engine.py::Factions.__init__",
    "faction_engine.py::Factions.clear_loan",
    "lattice/encounters.py::Encounters.complete_cast",
    "lattice/encounters.py::Encounters.complete_survey",
    "lattice/encounters.py::Encounters.select",
    "lattice/encounters.py::Encounters.trace",
    "lattice/engine.py::Lattice.jack_in",
    "lattice/engine.py::Lattice.leave",
    "lattice/engine.py::Lattice.reveal",
    "npcs/engine.py::Npcs.dispatch",
    "npcs/engine.py::Npcs.keep_truce",
    "private_cores.py::PrivateCores.on_login",
    "progression_engine.py::ProgressionEngine.grade5_notice",
    "progression_engine.py::ProgressionEngine.hostile_contact",
    "progression_engine.py::ProgressionEngine.sync_actor",
    "relay_passages.py::Passages.__init__.arrived",
    "relay_passages.py::Passages.begin",
}

SETTLES = {
    "apartments.py::Apartments.commit",
    "characters.py::Characters.take_card",
    "clinics.py::Clinics.operate",
    "combat/engine.py::Combat.die",
    "combat/engine.py::Combat.fire",
    "combat/engine.py::Combat.recover_at_vat",
    "combat/engine.py::Combat.respawn",
    "contract_engine.py::Contracts.subdued.propose",
    "contract_engine.py::Contracts.write",
    "contracts/scenes.py::Scenes.escorts",
    "dialogue_runtime.py::Dialogue.open",
    "dialogue_runtime.py::Dialogue.undo_meeting.restore",
    "drones.py::Drones.checkpoint",
    "drones.py::Drones.command",
    "drones.py::Drones.destroy.propose",
    "drones.py::Drones.objective",
    "drones.py::Drones.relocate_follow",
    "event_engine.py::Events.write",
    "event_views.py::Views.save",
    "faction_engine.py::Factions.propose",
    "faction_engine.py::Factions.reserve_stock",
    "faction_engine.py::Factions.service",
    "interlock.py::Interlock.commit",
    "lattice/encounters.py::Encounters.complete_cast",
    "lattice/encounters.py::Encounters.descend",
    "lattice/encounters.py::Encounters.lift",
    "market_engine.py::Trading.write",
    "npcs/engine.py::Npcs.died.propose",
    "private_cores.py::PrivateCores.complete_theft",
    "progression_engine.py::ProgressionEngine.record_discovery.propose",
    "progression_engine.py::ProgressionEngine.record_use.propose",
    "progression_engine.py::ProgressionEngine.spend",
    "relay_engine.py::Relays.write",
    "relay_passages.py::Passages.choose.execute",
    "salvage.py::Salvage.commit",
    "substances.py::Substances.refresh.propose",
}

WAKE_RECORD = "the identity's wake record, the one thing an unread body keeps (S48c1a)"

OTHER = {
    # Character storage itself.
    "characters.py::Characters.queue::outbox": "guard 1 itself",
    "app.py::Server._character_writes::outbox": "drains the outboxes; commerce effects pass can_commit first",
    "characters.py::Characters.create::queue:create": "the record is read: the creation commit (S48c1a)",
    "characters.py::Characters.create::identity()": "creation: card, receipts and debt go with the create effect",
    "characters.py::Characters.create::clone_debt": "creation copies the identity's debt onto the new character",
    "characters.py::Characters.input.proceed::queue:delete": "guard 1, and delete is refused for an unread body (S48c1a)",
    "characters.py::Characters.input.proceed::clone_debt": "delete of a stored character only (an unread body cannot start one)",
    "characters.py::Characters.committed::identities": "storage answered a create or delete",
    "characters.py::Characters.committed::identities-held": "storage answered a create or delete",
    "characters.py::Characters.committed::queue:identity": "clears the used serial from the wake record (review 6872808103)",
    "characters.py::Characters.__init__::identities": "loads the stored identities",
    "characters.py::Characters.identity::identities": "the accessor: creates an empty identity once",
    "characters.py::Characters.identity::identities-held": "the accessor itself",
    "characters.py::Characters.identity::queue:identity": "a new identity row",
    "characters.py::Characters.attach::identity()": "a stored character attaching; unread bodies never attach",
    "characters.py::Characters.connect::identity()": "reads the wake record on connect",
    "characters.py::Characters.promote::identity()": "the record is read: personhood for the new character",
    "characters.py::Characters.promote::identities": "clears the wake record once the character exists",
    "characters.py::Characters.me::identities-held": "read for the sheet (days since decant)",
    "characters.py::Characters.tick::identities-held":
        "personhood is calendar only and identity-scoped (game design 3.4), the same for any body",
    "characters.py::Characters.recover::identities": "returns at once for an unread body (write guard 1)",
    "characters.py::Characters.recover::clone_debt": "returns at once for an unread body (write guard 1)",
    # The wake record.
    "characters.py::Characters.enter_hall::identity()": WAKE_RECORD,
    "characters.py::Characters.enter_hall::queue:identity": WAKE_RECORD,
    "characters.py::Characters.disconnect::identities": WAKE_RECORD,
    "characters.py::Characters.disconnect::queue:identity": WAKE_RECORD,
    "characters.py::Characters.wake_input::identities": WAKE_RECORD,
    "characters.py::Characters.wake_input::queue:identity": WAKE_RECORD,
    "characters.py::Characters.take_card::identities": WAKE_RECORD + "; a character's card settles (guard 2)",
    "characters.py::Characters.take_card::queue:identity": WAKE_RECORD,
    "characters.py::Characters.lesson::identities": WAKE_RECORD + "; lesson facts (S48c1b)",
    "characters.py::Characters.lesson::queue:identity": WAKE_RECORD + "; lesson facts (S48c1b)",
    # Commerce and its effects.
    "commerce.py::Commerce.settle::outbox": "guard 2 itself",
    "commerce.py::Commerce.propose::outbox": "guard 2: propose refuses an unread body",
    "commerce.py::Commerce.tick::outbox": "expiry of caches; no player patch",
    "commerce.py::Commerce.committed::identities": "applies a committed effect, which passed can_commit",
    "commerce.py::Commerce.committed::identities-held": "applies a committed effect, which passed can_commit",
    "apartments.py::Apartments.commit::outbox": G2_OUTBOX,
    "combat/engine.py::Combat.die::outbox": G2_OUTBOX + "; the killer's patch is a player_patches recipient",
    "combat/engine.py::Combat.die::clone_debt": "set on a deep copy sent with the settle",
    "interlock.py::Interlock.commit::outbox": G2_OUTBOX,
    "interlock.py::Interlock.finish_cut::outbox": G2_OUTBOX + "; patches are player_patches recipients",
    "lattice/encounters.py::Encounters.descend::outbox": G2_OUTBOX,
    "lattice/encounters.py::Encounters.lift::outbox": G2_OUTBOX + "; an unread body's lift returns before it",
    "npcs/engine.py::Npcs.died.propose::outbox": G2_OUTBOX,
    "private_cores.py::PrivateCores.complete_theft::outbox": G2_OUTBOX + "; the thief is a player_patches recipient",
    "private_cores.py::PrivateCores.report_theft::outbox": G2_OUTBOX,
    "salvage.py::Salvage.commit::outbox": G2_OUTBOX,
    "contract_engine.py::Contracts.finish_services::identities-held": "a default for a value that is deep-copied",
    "progression_engine.py::ProgressionEngine.sheet::identities-held": "read for the sheet (days since decant)",
    # Moderation.
    "chat.py::Chat.report::outbox": "a chat report row may name an unread body (technical lead, #241): moderation, no character row",
}


def expected() -> dict[str, str]:
    table = dict(OTHER)
    table.update({site + "::queue:save": G1 for site in SAVES})
    table.update({site + "::settle": G2 for site in SETTLES})
    return table


def test_every_writer_of_player_or_identity_state_is_accounted_for() -> None:
    found, table = set(writer_sites()), expected()
    new, gone = sorted(found - table.keys()), sorted(table.keys() - found)
    assert not new, ("New writers of player or identity state. Check each against the S48 write guards "
                     "(an unread body must never be stored), then add it with its reason:\n  " + "\n  ".join(new))
    assert not gone, "Writers no longer in the source; remove them from the table:\n  " + "\n  ".join(gone)


def test_no_writer_sends_an_action_name_the_table_cannot_see() -> None:
    assert not [key for key in writer_sites() if key.endswith("::queue:?")]


def test_guard_1_drops_save_and_delete_for_an_unread_body(game: HeadlessServer) -> None:
    client = game.connect()
    game.step(2)
    manager = game.core.characters
    body = manager.players[client.session.player_id]
    before = len(manager.outbox)
    for action in ("save", "delete"):
        manager.queue(action, body.bbs_user_id, body, immediate=True)
    assert len(manager.outbox) == before


def test_guard_2_refuses_settle_and_any_effect_naming_an_unread_body(game: HeadlessServer) -> None:
    client, other = game.connect(), game.connect({"user_id": 2, "handle": "Other"})
    create(game, other, name="Noor", card="none")
    game.step(2)
    manager, commerce = game.core.characters, game.core.commerce
    body = manager.players[client.session.player_id]
    character = manager.players[other.session.player_id]
    assert manager.unread(body.id) and not manager.unread(character.id)
    assert not commerce.settle(body, {"chits_hand": 5}, dict(commerce.items), commerce.caches, commerce.serial, lambda ok: None)
    assert not commerce.can_commit({"player_id": body.id})
    assert not commerce.can_commit({"player_id": character.id, "player_patches": {body.id: {"chits_hand": 5}}})
    assert commerce.can_commit({"player_id": character.id})


def test_recover_leaves_an_unread_body_and_its_identity_alone(game: HeadlessServer) -> None:
    client = game.connect()
    game.step(2)
    manager = game.core.characters
    body = manager.players[client.session.player_id]
    body.progress["sleeper_combat"] = True
    debt, place, before = manager.identity(body.bbs_user_id).get("clone_debt"), (body.zone, body.tile), len(manager.outbox)
    manager.recover(body)
    assert manager.identity(body.bbs_user_id).get("clone_debt") == debt
    assert (body.zone, body.tile) == place and len(manager.outbox) == before
