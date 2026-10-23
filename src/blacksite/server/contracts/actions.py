"""Game 9: verified physical objective actions and interruptible channels."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from blacksite.content.schema import StageTarget
from blacksite.server.contracts.engine import Fact, target_key
from blacksite.server.inventory import Inventory
from blacksite.server.items import make_item
from blacksite.server.npcs.templates import SUBDUE_SHOCK
from blacksite.server.protocol import Frame
from blacksite.server.sessions import Session
from blacksite.server.clock import TICK_HZ


@dataclass
class Channel:
    instance: str
    stage: str
    attempt: int
    target: StageTarget
    zone: str
    tile: tuple[int, int]
    last_hit: int | float | None
    until: int


class Actions:
    def __init__(self, owner: Any) -> None:
        self.owner, self.game, self.world = owner, owner.game, owner.world
        self.channels: dict[str, Channel] = {}
        self.requests: dict[str, list[str]] = {}

    def near(self, actor: Any, target: StageTarget) -> bool:
        if target.zone != actor.zone:
            return False
        tile = target.tile
        if target.object:
            obj = self.world.zones[actor.zone].objects.get(target.object)
            if not obj or not self.world.object_access(actor, obj.spec):
                return False
            tile = obj.spec.tile
        return tile is not None and max(abs(actor.x-tile[0]), abs(actor.y-tile[1])) <= 1

    def perform(self, session: Session, iid: str, target: StageTarget, finished: bool = False) -> None:
        owner = self.owner
        if not owner.commerce.ready(session) or owner.commerce.pending:
            raise ValueError('Return to the objective when the current action settles.')
        player = self.game.players[session.player_id]
        instance = owner.state.engine.instances[iid]
        if (instance.state != 'active' or player.id in instance.withdrawn
                or player.id not in {p.player for p in instance.roster}
                or instance.expires_at is not None and owner.now() >= instance.expires_at):
            raise ValueError('That objective is no longer active for you.')
        progress = instance.stages[instance.index]
        if target not in progress.targets:
            raise ValueError('Choose a target on the current objective card.')
        stage = progress.stage
        actor = self.game.combat.actor(player)
        if not self.near(actor, target):
            raise ValueError('Move next to the labelled objective.')
        if stage.seconds and not finished:
            if actor.behaviour.get('channel') or session.id in self.channels:
                raise ValueError('Finish or cancel the current channel first.')
            self.channels[session.id] = Channel(iid, stage.id, progress.attempt, target,
                actor.zone, actor.position, actor.cooldowns.get('last_hit'),
                owner.clock.now_tick()+round(stage.seconds*TICK_HZ))
            actor.behaviour['channel'] = {'owner': 'contract', 'label': stage.label or stage.verb,
                                          'remaining': stage.seconds}
            self.world.zones[actor.zone].revision += 1
            return
        draft, recipient = owner.state.fork(), deepcopy(player)
        items, serial = deepcopy(owner.commerce.items), owner.commerce.serial
        inventory = Inventory(items, owner.content.items, owner.progression.modifiers(player).secured_slots)
        subject = target_key(target)
        need = stage.requires_item or (target.item if stage.completion == 'delivered' else None)
        if need:
            supplied = next((item for item in items.values() if item.owner == player.id
                and item.mission == iid and item.template == need and item.id in recipient.inventory), None)
            if supplied is None:
                raise ValueError('Carry the bound '+owner.content.items[need].name+' from this job first.')
            if stage.verb == 'plant' or stage.completion == 'delivered':
                subject = f'{supplied.id}:unit:{supplied.stack}'
                inventory.remove(recipient, supplied.id, 1, lambda: '', mission=iid)
        if stage.verb == 'fetch' and stage.completion == 'carried':
            if target.item is None:
                raise ValueError('That pickup is not commissioned.')
            serial += 1
            supplied = make_item(f'{owner.origin}:item:{serial}', owner.content.items[target.item],
                                 player.id, owner.clock.now_utc().isoformat())
            supplied.bound, supplied.secured = True, False
            supplied.mission, supplied.mission_stage = iid, f'{stage.id}:{progress.attempt}'
            inventory.add(recipient, supplied)
            subject = supplied.id
        if stage.verb not in ('survey', 'fetch', 'plant', 'hack'):
            raise ValueError('Use the objective actor or its Lattice control.')
        fact = Fact(player.id, stage.verb, stage.completion, target, subject,
            f'{instance.id}:{stage.receipt_key}:{progress.attempt}:{subject}', instance=iid,
            stage=stage.id, attempt=progress.attempt)
        if not draft.observe(fact, owner.now()):
            raise ValueError('That objective action was already recorded.')
        owner.write(draft, {player.id: {'inventory': recipient.inventory}}, items=items, serial=serial,
                    callback=lambda success: owner.log(player.id, 'Objective recorded.' if success else
                                                       'The action could not be saved. Your supplies remain.'))

    def interact_npc(self, session: Session, iid: str) -> bool:
        owner, pid = self.owner, session.player_id
        instance = owner.state.engine.instances[iid]
        progress = instance.stages[instance.index]
        source = self.game.combat.actor(self.game.players[pid])
        for index, target in enumerate(progress.targets):
            actor = self.world.actors.get(owner.scenes.unit(instance, progress, index))
            if not actor or actor.zone != source.zone or max(abs(actor.x-source.x), abs(actor.y-source.y)) > 1:
                continue
            if progress.stage.verb == 'clear' and progress.stage.resolution == 'subdue':
                if source.id in self.game.npcs.restraints:
                    return True
                if not self.game.npcs.subdue(source, actor):
                    raise ValueError(f'Bring the target to {SUBDUE_SHOCK} shock, then press E for restraint.')
                return True
            if progress.stage.verb == 'escort':
                if not actor.behaviour.get('willing'):
                    raise ValueError('That person has not agreed to follow.')
                if owner.commerce.pending:
                    raise ValueError('The city is busy. Try again.')
                draft = owner.state.fork()
                record = draft.engine.instances[iid].runtime.setdefault('actors', {}).setdefault(actor.id, {})
                record['escort'] = pid
                def committed(success: bool, body: Any = actor) -> None:
                    if success:
                        self.game.npcs.escort(source, body)
                        owner.log(pid, 'The willing escort follows you. Lead them to the marked destination.')
                owner.write(draft, callback=committed)
                return True
        return False

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        owner = self.owner
        name = frame.data.get('name', '') if frame.type == 'intent' else ''
        key = frame.data.get('k', '') if frame.type == 'key' else ''
        typed = name in ('evidence.inspect', 'contract.perform', 'work_order.perform')
        if (session.player_id in self.game.npcs.restraints
                and (name == 'menu_close' or key.lower() in ('escape', 'b'))):
            self.game.npcs.restraints.pop(session.player_id)
            player = self.game.players.get(session.player_id)
            actor = self.game.combat.actor(player) if player else None
            if actor and actor.behaviour.get('channel', {}).get('owner') == 'restraint':
                actor.behaviour.pop('channel')
            return True
        if session.id in self.channels and (name == 'menu_close' or key.lower() in ('escape', 'b')):
            self.cancel(session)
            return True
        if not typed and name != 'interact' and key.lower() != 'e':
            return False
        if (not owner.commerce.ready(session) or session.id in owner.sim.external_views
                or session.pending_prompts or session.id in owner.panels.menus):
            return False
        try:
            if typed:
                request = frame.data.get('request_id', '')
                if (not request or request in self.requests.get(session.id, [])
                        or frame.data.get('expected_revision') != session.view_revision):
                    return True
                self.requests.setdefault(session.id, []).append(request)
                self.requests[session.id] = self.requests[session.id][-128:]
            wanted = frame.data.get('args', {}).get('instance', '')
            actor = self.game.combat.actor(self.game.players[session.player_id])
            for iid, instance in owner.state.engine.instances.items():
                if (instance.state != 'active' or wanted and wanted != iid
                        or session.player_id not in {p.player for p in instance.roster} - instance.withdrawn):
                    continue
                stage = instance.stages[instance.index].stage
                if stage.verb in ('clear', 'escort'):
                    if self.interact_npc(session, iid):
                        return True
                    continue
                if stage.target.kind in ('core_room', 'core_control', 'cell'):
                    continue
                for target in instance.stages[instance.index].targets:
                    if self.near(actor, target):
                        self.perform(session, iid, target)
                        return True
            if typed:
                raise ValueError('Move next to an active objective and inspect its current card.')
        except (ValueError, KeyError, TypeError) as exc:
            owner.commerce.toast(session, str(exc) if isinstance(exc, ValueError) else 'That objective changed.')
            return True
        return False

    def cancel(self, session: Session) -> None:
        self.channels.pop(session.id, None)
        player = self.game.players.get(session.player_id)
        actor = self.game.combat.actor(player) if player else None
        if actor and actor.behaviour.get('channel', {}).get('owner') == 'contract':
            actor.behaviour.pop('channel')
            if actor.zone:
                self.world.zones[actor.zone].revision += 1

    def tick(self, tick: int) -> None:
        for sid, channel in tuple(self.channels.items()):
            session = self.game.sessions.active.get(sid)
            player = self.game.players.get(session.player_id) if session else None
            actor = self.game.combat.actor(player) if player else None
            instance = self.owner.state.engine.instances.get(channel.instance)
            progress = instance.stages[instance.index] if instance and instance.state == 'active' else None
            valid = (session and actor and self.owner.commerce.ready(session)
                and actor.behaviour.get('channel', {}).get('owner') == 'contract'
                and (actor.zone, actor.position, actor.cooldowns.get('last_hit')) ==
                    (channel.zone, channel.tile, channel.last_hit)
                and progress and progress.stage.id == channel.stage and progress.attempt == channel.attempt)
            if not valid:
                if session:
                    self.cancel(session)
                else:
                    self.channels.pop(sid, None)
                continue
            actor.behaviour['channel']['remaining'] = max(0, (channel.until-tick)/TICK_HZ)
            if tick >= channel.until and not self.owner.commerce.pending:
                self.cancel(session)
                try:
                    self.perform(session, channel.instance, channel.target, finished=True)
                except (ValueError, KeyError) as exc:
                    self.owner.commerce.toast(session, str(exc))
        self.requests = {sid: rows for sid, rows in self.requests.items() if sid in self.game.sessions.active}
