"""Game 9: verified physical objective actions and interruptible channels."""

from copy import deepcopy
from collections import Counter
from dataclasses import dataclass
from typing import Any

from blacksite.content.schema import Stage, StageTarget
from blacksite.server.contracts.engine import Fact, Instance, Progress, matches, target_key
from blacksite.server.inventory import Inventory
from blacksite.server.items import ItemInstance, make_item
from blacksite.server.players import Player
from blacksite.server.lattice.presence import Presence, Procedure
from blacksite.server.lattice.programs import ticks
from blacksite.server.npcs.templates import SUBDUE_SHOCK
from blacksite.server.protocol import Frame
from blacksite.server.sessions import Session
from blacksite.server.clock import TICK_HZ

PLANT_SECONDS = 3  # Game 9.1: physical and core planting.
PLANT_TRACE = 10  # Game 9.1: core planting, where trace applies.


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

    @staticmethod
    def required(stage: Stage) -> str | None:
        return stage.requires_item or (stage.target.item if stage.verb == 'plant' or stage.completion == 'delivered' else None)

    def carried(self, player: Player, iid: str, template: str | None) -> ItemInstance | None:
        return next((item for item in self.owner.commerce.items.values()
            if item.owner == player.id and item.mission == iid and item.template == template
            and item.id in player.inventory), None)

    def supplies(self, instance: Instance) -> tuple[StageTarget, ...]:
        stage = instance.stages[instance.index].stage
        need = self.required(stage)
        if need is None:
            return ()
        result = []
        for previous in instance.stages[:instance.index]:
            for target in previous.targets:
                if previous.stage.verb == 'fetch' and previous.stage.completion == 'carried' and target.item == need:
                    result.append(target)
                elif previous.stage.input == 'lift':
                    data = self.owner.mission_data(instance, target)
                    if data and data.scope == 'mission' and data.kind == 'item' and data.asset == need:
                        result.append(target)
        return tuple(result)

    def reissue(self, session: Session, iid: str, target: StageTarget) -> None:
        owner, pid = self.owner, session.player_id
        instance = next((job for job, _ in owner.current_jobs(pid) if job.id == iid), None)
        if (not instance or not owner.commerce.ready(session) or owner.commerce.pending
                or target not in self.supplies(instance)
                or not self.near(self.game.combat.actor(self.game.players[pid]), target)):
            raise ValueError('Return to this job\'s labelled supply point.')
        player = self.game.players[pid]
        need = self.required(instance.stages[instance.index].stage)
        if self.carried(player, iid, need):
            raise ValueError('You already carry this job\'s supplied item.')
        recipient, items = deepcopy(player), deepcopy(owner.commerce.items)
        serial = owner.commerce.serial+1
        supplied = make_item(f'{owner.origin}:item:{serial}', owner.content.items[need], pid,
                             owner.clock.now_utc().isoformat())
        supplied.bound, supplied.secured, supplied.mission = True, False, iid
        progress = instance.stages[instance.index]
        supplied.mission_stage = f'{progress.stage.id}:{progress.attempt}'
        Inventory(items, owner.content.items, owner.progression.modifiers(player).secured_slots).add(recipient, supplied)
        owner.write(owner.state.fork(), {pid: {'inventory': recipient.inventory}}, items=items, serial=serial,
            callback=lambda success: owner.log(pid, 'Bound supply reissued.' if success else
                                               'The supply could not be saved. Try again.'))

    def inspect_presence(self, presence: Presence) -> None:
        """Capture the actual place and accepted attempt before queuing a write."""
        owner = self.owner
        if owner.lat.presences.get(presence.player_id) is not presence or presence.descent:
            return
        target = (StageTarget('core_room', core=presence.core, room=presence.room)
                  if presence.instance else StageTarget('cell', sector=presence.sector, cell=presence.cell))
        facts = []
        for instance, progress in owner.current_jobs(presence.player_id):
            stage = progress.stage
            if stage.verb != 'survey' or stage.input != 'inspect' or not any(matches(t, target) for t in progress.targets):
                continue
            subject = target_key(target)
            facts.append(Fact(presence.player_id, 'survey', stage.completion, target, subject,
                f'{instance.id}:{stage.id}:{progress.attempt}:inspect:{subject}',
                instance=instance.id, stage=stage.id, attempt=progress.attempt))
        if not facts:
            return
        def execute() -> None:
            draft = owner.state.fork()
            changed = False
            for fact in facts:
                changed = bool(owner.observe(draft, fact)) or changed
            if changed:
                owner.write(draft)
        owner.commerce.enqueue_system(execute)

    def plant_target(self, presence: Presence, iid: str) -> tuple[Instance, Progress, StageTarget]:
        owner = self.owner
        if owner.lat.presences.get(presence.player_id) is not presence:
            raise ValueError('Return to the active core objective.')
        for instance, progress in owner.current_jobs(presence.player_id):
            if instance.id != iid or progress.stage.verb != 'plant':
                continue
            quotas = Counter(target_key(t) for t in progress.targets)
            for target in progress.targets:
                if (target.kind == 'core_room' and target.core == presence.core and target.room == presence.room
                        and progress.counts.get(target_key(target), 0) < quotas[target_key(target)]):
                    return instance, progress, target
        raise ValueError('This is not your active planting room.')

    def core_rows(self, presence: Presence) -> list[dict[str, Any]]:
        result = []
        for instance, progress in self.owner.current_jobs(presence.player_id):
            if progress.stage.verb != 'plant':
                continue
            try:
                self.plant_target(presence, instance.id)
            except ValueError:
                continue
            result.append({'id': 'plant:'+instance.id, 'cells': [progress.stage.label or 'Plant supplied item',
                f'{PLANT_SECONDS} s / {PLANT_TRACE} trace where applicable']})
        return result

    def start_plant(self, presence: Presence, iid: str) -> None:
        owner, encounters = self.owner, self.owner.lat.encounters
        if not encounters.idle(presence) or owner.commerce.pending:
            raise ValueError('Let the current action settle first.')
        instance, progress, target = self.plant_target(presence, iid)
        player = self.game.players[presence.player_id]
        need = self.required(progress.stage)
        if not need or not self.carried(player, iid, need):
            raise ValueError('Carry the bound supply from this job\'s labelled pickup first. Q shows the source.')
        presence.procedure = Procedure('plant', iid, owner.clock.now_tick()+ticks(PLANT_SECONDS),
            encounters.location(presence)[0], encounters.hit_serial(presence),
            source=f'{progress.stage.id}:{progress.attempt}')
        before = presence.trace
        encounters.trace(presence, PLANT_TRACE)
        encounters.log(presence, f'Planting: {PLANT_SECONDS} s. Trace change: +{presence.trace-before:g}. Esc cancels.')

    def finish_plant(self, presence: Presence, procedure: Procedure) -> None:
        owner = self.owner
        instance, progress, target = self.plant_target(presence, procedure.target)
        if procedure.source != f'{progress.stage.id}:{progress.attempt}':
            raise ValueError('The planting objective changed. Your supply remains.')
        player = self.game.players[presence.player_id]
        supplied = self.carried(player, instance.id, self.required(progress.stage))
        if supplied is None:
            raise ValueError('Your bound supply is no longer here.')
        recipient, items, draft = deepcopy(player), deepcopy(owner.commerce.items), owner.state.fork()
        subject = f'{supplied.id}:unit:{supplied.stack}'
        Inventory(items, owner.content.items, owner.progression.modifiers(player).secured_slots).remove(
            recipient, supplied.id, 1, lambda: '', mission=instance.id)
        fact = Fact(player.id, 'plant', 'planted', target, subject,
            f'{instance.id}:{progress.stage.receipt_key}:{progress.attempt}:{subject}',
            instance=instance.id, stage=progress.stage.id, attempt=progress.attempt)
        if not owner.observe(draft, fact):
            raise ValueError('That planting action was already recorded.')
        owner.write(draft, {player.id: {'inventory': recipient.inventory}}, items=items,
            callback=lambda success: owner.log(player.id, 'Objective planted.' if success else
                                               'The plant could not be saved. Your supply remains.'))

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
        seconds = owner.duration(player.id, stage)
        if seconds and not finished:
            if actor.behaviour.get('channel') or session.id in self.channels:
                raise ValueError('Finish or cancel the current channel first.')
            self.channels[session.id] = Channel(iid, stage.id, progress.attempt, target,
                actor.zone, actor.position, actor.cooldowns.get('last_hit'),
                owner.clock.now_tick()+round(seconds*TICK_HZ))
            actor.behaviour['channel'] = {'owner': 'contract', 'label': stage.label or stage.verb,
                                          'remaining': seconds}
            self.world.zones[actor.zone].revision += 1
            return
        draft, recipient = owner.state.fork(), deepcopy(player)
        items, serial = deepcopy(owner.commerce.items), owner.commerce.serial
        inventory = Inventory(items, owner.content.items, owner.progression.modifiers(player).secured_slots)
        subject = target_key(target)
        need = self.required(stage)
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
        if not owner.observe(draft, fact):
            raise ValueError('That objective action was already recorded.')
        owner.write(draft, {player.id: {'inventory': recipient.inventory}}, items=items, serial=serial,
                    callback=lambda success: owner.log(player.id, 'Objective recorded.' if success else
                                                       'The action could not be saved. Your supplies remain.'),
                    linked_control=(player.id, stage.linked_control) if stage.linked_control else None)

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
                if actor.behaviour.get('escort') == pid:
                    continue  # Repeated E assigns the next willing group member.
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
            if not typed and owner.effects.cache(session):
                return True
            for iid, instance in owner.state.engine.instances.items():
                if (instance.state != 'active' or wanted and wanted != iid
                        or session.player_id not in {p.player for p in instance.roster} - instance.withdrawn):
                    continue
                stage = instance.stages[instance.index].stage
                if self.required(stage) and not self.carried(self.game.players[session.player_id], iid, self.required(stage)):
                    for source in self.supplies(instance):
                        if self.near(actor, source):
                            self.reissue(session, iid, source)
                            return True
                if stage.verb in ('clear', 'escort'):
                    if self.interact_npc(session, iid):
                        return True
                    continue
                if stage.target.kind in ('core_room', 'core_control', 'cell', 'silt_data'):
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
