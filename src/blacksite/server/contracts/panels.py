"""UI 11: server-owned contract cards, consent and acquired evidence."""

from dataclasses import dataclass
from math import ceil
import textwrap
from typing import Any

from blacksite.server.contracts.engine import Instance, Payment
from blacksite.server.contracts.requirements import describe as describe_requirement
from blacksite.server.protocol import Frame
from blacksite.server.commerce import CommerceMenu
from blacksite.server.sessions import Session
from blacksite.server.wake import menu
from blacksite.server.world.simulation import MENU_TIMEOUT_SECONDS
from blacksite.server.clock import TICK_HZ
from blacksite.server.crews import GUARD_SECONDS
from blacksite.server.npcs.templates import SUBDUE_SHOCK


@dataclass
class Panel:
    opened: int
    target: str = ''
    handler: str = ''
    tab: str = 'jobs'
    cursor: int = 0
    page: int = 0
    confirmation: tuple[str, str, str] | None = None
    prose: bool = False


def takes_turnin(handler: str, instance: Instance) -> bool:
    return handler == instance.giver or (handler == 'vesper' and not instance.service)


def payment(payment: Payment) -> str:
    text = f'{payment.chits} chits; {payment.xp} XP'
    if payment.standing:
        text += '; ' + ', '.join(f'{fid} {value:+d}' for fid, value in payment.standing.items())
    if payment.items or payment.programs:
        text += '; '+', '.join((*payment.items, *payment.programs))
    return text


def consequences(job: Any) -> list[str]:
    lines = [job.consequence] if job.consequence else []
    if job.branch_group and job.branch:
        lines.append(f'Personal choice: {job.branch}. The other {job.branch_group} route closes.')
    if job.permit_scope:
        permit = job.permit_scope
        lines.append(f'Effect: {permit.kind} at {permit.target}; {permit.expiry_seconds} s.')
    return lines


class Panels:
    def __init__(self, owner: Any) -> None:
        self.owner, self.game, self.sim = owner, owner.game, owner.sim
        self.menus: dict[str, Panel] = {}
        self.requests: dict[str, list[str]] = {}

    def station(self, session: Session, target: str) -> str:
        if not self.owner.commerce.ready(session):
            raise ValueError('Return to your body before visiting a contract board.')
        obj = self.owner.commerce.nearby(session, target)
        handler = obj.spec.params.get('contract_handler', '')
        if handler not in (*self.owner.content.factions, 'vesper'):
            raise ValueError('That object is not a commissioned contract board.')
        return handler

    def close(self, session: Session) -> None:
        self.menus.pop(session.id, None)
        self.sim.external_views.pop(session.id, None)
        self.sim.published.pop(session.id, None)
        session.needs_full_view = True

    def rows(self, session: Session, panel: Panel) -> list[dict[str, Any]]:
        owner, pid = self.owner, session.player_id
        if panel.tab == 'journal':
            rows = [{'id': eid, 'cells': [record['observation']]}
                    for eid, record in owner.state.journal.get(pid, {}).items()]
            if owner.effects.patrols(pid):
                rows.append({'id': 'intel:patrol', 'cells': ['Published patrol telemetry']})
            return rows
        result = [{'id': p.id, 'cells': ['Proposal', owner.content.contracts[p.offer.template].name or p.offer.template]}
                  for p in owner.proposals.values() if pid in p.roster and panel.tab == 'jobs']
        for iid, job in owner.state.engine.instances.items():
            if pid not in {p.player for p in job.roster}:
                continue
            retired = job.state == 'turned_in' or (pid in job.withdrawn and (job.service or job.state == 'complete' or job.failure == 'expired'))
            if retired != (panel.tab == 'done'):
                continue
            name = owner.content.contracts[job.template].name or job.template
            result.append({'id': iid, 'cells': ['withdrawn' if pid in job.withdrawn else job.state, name]})
        if panel.handler and panel.tab == 'jobs':
            self.station(session, panel.target)
            actor = owner.game.combat.actor(owner.game.players[pid])
            for sid, node in owner.state.services.nodes.items():
                service = owner.content.services[sid]
                if service.zone == actor.zone and owner.content.contracts[service.contract].giver == panel.handler:
                    result.append({'id': 'service:'+sid, 'cells': [node.state, service.name]})
            for tid, job in owner.state.engine.templates.items():
                if (job.story and (job.giver == panel.handler or panel.handler == 'vesper' and not job.service)
                        and tid not in owner.state.engine.completed.get(pid, set())
                        and not owner.state.engine.helper_for(job, pid)
                        and not owner.requirements(pid, job, broker=panel.handler == 'vesper')
                        and not any(j.template == tid and j.state != 'turned_in' and pid in {p.player for p in j.roster}
                                    for j in owner.state.engine.instances.values())):
                    result.append({'id': tid, 'cells': ['Story', job.name or job.id]})
            for offer in owner.offers(panel.handler):
                job = owner.state.engine.templates[offer.template]
                result.append({'id': offer.id, 'cells': ['Offer', job.name or job.id]})
        return result

    def card(self, session: Session, panel: Panel, selected: str) -> tuple[list[str], list[dict[str, str]]]:
        owner, pid = self.owner, session.player_id
        actions = [{'key': 'j', 'label': 'journal' if panel.tab != 'journal' else 'jobs'}]
        if panel.tab != 'journal':
            actions.append({'key': 'd', 'label': 'jobs' if panel.tab == 'done' else 'done'})
        if panel.handler and panel.target:
            obj = owner.commerce.nearby(session, panel.target)
            if obj.spec.params.get('trade_counter') and not panel.confirmation:
                actions.append({'key': 'v', 'label': 'trade'})
        if panel.tab == 'journal':
            if selected == 'intel:patrol':
                return ['Observed: current published NPC patrol routes.',
                        'Source says: committed local telemetry.',
                        'Next action: use the route; E still handles ordinary defenses.',
                        *owner.effects.patrols(pid)], actions
            row = owner.state.journal.get(pid, {}).get(selected)
            if not row:
                return ['Inspect a labelled objective to acquire a record.'], actions
            if panel.prose:
                asset = owner.content.text.get(row['asset'])
                return (asset.body.splitlines() if asset else ['No additional source text.']), actions
            actions += [{'key': 'p', 'label': 'source text'}]
            where = row['location']
            place = ', '.join(str(where[k]) for k in ('zone', 'object', 'core', 'room', 'data') if where.get(k))
            return [f"Observed: {row['observation']}", f"Source says: {row['source']}: {row['claim']}",
                    f"Open question: {row['question'] or 'No further question recorded.'}",
                    f"Next action: {row['next_action'] or 'Check the current contract objective.'}",
                    'Where: '+place, 'Publication: '+(row['publication'] or 'not published')], actions
        if selected.startswith('service:') and selected[8:] in owner.state.services.nodes:
            sid = selected[8:]
            node, service = owner.state.services.nodes[sid], owner.content.services[selected[8:]]
            job = owner.content.contracts[service.contract]
            quoted = owner.state.engine.offer(job, 'service-preview', node.fault_expires).reward.scaled(
                1, False, owner.game.players[pid].archetype == 'operator')
            detail = [service.name+': '+node.state, service.fault_label,
                'Your reward: '+payment(quoted), 'Reserve for 10 min; completed allocation lasts 20 min.',
                'Return: '+service.safe_return]
            for allocation in service.allocations:
                detail.append(allocation.label+': '+allocation.detail)
            if node.state == 'fault':
                detail.append(f'NPC restoration in {max(0, ceil(node.fault_expires-owner.now()))} s.')
                actions += [{'key': '1', 'label': 'common'}, {'key': '2', 'label': 'reserve'},
                            {'key': '3', 'label': 'common crew'}, {'key': '4', 'label': 'reserve crew'}]
            elif node.state == 'repairing':
                detail += ['Reserved allocation: '+node.allocation,
                    'Workers: '+', '.join(owner.game.players[p].name if p in owner.game.players else 'Departed worker' for p in node.roster),
                    f'Reservation: {max(0, ceil(node.reserved_until-owner.now()))} s']
            elif node.state == 'allocated':
                detail += ['Allocation: '+node.allocation, f'Expiry: {max(0, ceil(node.allocation_expires-owner.now()))} s']
            return detail, actions
        if selected in owner.proposals:
            proposal = owner.proposals[selected]
            job = owner.state.engine.templates[proposal.offer.template]
            participant = owner.participant(pid)
            helper = owner.state.engine.helper_for(job, pid)
            quoted = (Payment(0, 0, {}, 'explicit') if helper else
                proposal.offer.reward.scaled(len(proposal.roster), job.crew_scaling and not job.story and not job.service,
                                                  participant.archetype == 'operator'))
            detail = ['Terms: '+(job.name or job.id), 'Your reward: '+payment(quoted),
                'Approach: '+(job.approach_label if proposal.approach == 'default' else
                              next(a.label for a in job.approaches if a.id == proposal.approach)),
                'Roster: '+', '.join(owner.game.players[p].name for p in proposal.roster),
                f'Consent: {len(proposal.consent)}/{len(proposal.roster)}. No slots or supplies spent yet.']
            detail.append(f'Contribute an objective action or guard nearby for {GUARD_SECONDS} s to earn the reward. Late joins earn nothing.')
            if helper:
                detail.append('Helper: no new payout; your earlier personal choice stays.')
            else:
                detail += consequences(job)
            if proposal.service:
                service = owner.content.services[proposal.service]
                chosen = next(a for a in service.allocations if a.id == proposal.allocation)
                other = next(a for a in service.allocations if a.id != proposal.allocation)
                detail += ['Allocation: '+chosen.label+': '+chosen.detail,
                    'Foregone: '+other.label+': '+other.detail,
                    'Reservation starts with the committed roster; 10 min, never extended.',
                    'Return: '+service.safe_return]
            detail.append('A verified objective contribution is required for a reward.')
            if pid not in proposal.consent:
                actions += [{'key': 'a', 'label': 'accept terms'}]
            if proposal.creator == pid and set(proposal.roster) == proposal.consent:
                actions += [{'key': 's', 'label': 'start'}]
            return detail, actions
        if selected in owner.state.engine.instances:
            instance = owner.state.engine.instances[selected]
            participant = next(p for p in instance.roster if p.player == pid)
            helper = owner.state.engine.helper(instance, participant)
            detail = ['Your reward: '+payment(owner.state.engine.quote(instance, participant)),
                      'Roster: '+', '.join(owner.game.players[p.player].name
                          if p.player in owner.game.players else 'Departed worker' for p in instance.roster)]
            if instance.expires_at is not None:
                detail.append(f'Deadline: {max(0, ceil(instance.expires_at-owner.now()))} s')
            else:
                detail.append('Story: no overall deadline.')
            if instance.state == 'active':
                progress = instance.stages[instance.index]
                target = progress.stage.target
                detail.insert(0, 'Next: '+(progress.stage.label or progress.stage.verb)+'; '+
                    ', '.join(str(v) for v in (target.zone, target.object, target.core, target.room,
                                              target.sector, target.band, target.data, target.npc, target.item) if v))
                detail.insert(1, f'Progress: {sum(progress.counts.values())}/{len(progress.targets)}; '
                    +('retry allowed' if progress.stage.retry else 'no retry'))
                restraint = progress.stage.verb == 'clear' and progress.stage.resolution == 'subdue'
                seconds = owner.duration(pid, progress.stage)
                cost = f'{SUBDUE_SHOCK} shock required; no fee.' if restraint else owner.action_cost(progress.stage)
                detail.insert(2, f'Action: {seconds:g} s; {cost}')
                if progress.stage.window_seconds and progress.started_at is not None:
                    left = max(0, ceil(progress.started_at+progress.stage.window_seconds-owner.now()))
                    detail.insert(2, f'Field window: {left} s remaining. Failure returns to the listed launch checkpoint.')
                if progress.stage.destination:
                    dest = progress.stage.destination
                    detail.insert(1, 'Destination: '+', '.join(str(v) for v in (dest.zone, dest.object, dest.tile) if v is not None))
                supplies = owner.actions.supplies(instance)
                if supplies:
                    source = supplies[0]
                    verb = 'E reissues at ' if source.zone else 'lift a mission copy at '
                    detail.insert(3, 'Missing supply? '+verb+', '.join(str(v)
                        for v in (source.zone, source.object, source.tile, source.core, source.room,
                                  source.sector, source.band, source.data) if v is not None)+'. Bound copies cannot be sold.')
            elif instance.state == 'complete':
                destination = instance.giver+"'s board" if instance.story or instance.service else "the Tin Halo or "+instance.giver+"'s board"
                detail.insert(0, 'Next: return to '+destination+'.')
                if takes_turnin(panel.handler, instance) and pid not in instance.withdrawn:
                    if instance.options:
                        if not helper and pid not in instance.paid:
                            for index, (option, terms) in enumerate(instance.options.items(), 1):
                                actions.append({'key': str(index), 'label': terms['label']})
                                detail.append(terms['label']+': '+payment(owner.state.engine.quote(instance, participant, option)))
                        else:
                            detail.append('Eligible participants record their own publication choice.')
                    else:
                        actions.append({'key': 't', 'label': 'turn in'})
            elif instance.state == 'failed':
                detail.insert(0, 'Stopped: '+instance.failure)
                if pid not in instance.withdrawn and instance.index < len(instance.stages) and instance.stages[instance.index].stage.retry:
                    actions.append({'key': 'r', 'label': 'retry stage'})
            if helper:
                detail.append('Helper: this story reward was already received. No new payout or changed personal choice.')
            if (pid in instance.withdrawn and not instance.service and instance.state in ('active', 'failed')
                    and instance.failure != 'expired'):
                actions.append({'key':'r', 'label':'resume original job'})
                detail.insert(0, 'Withdrawn. R resumes your original roster and terms; completed stages stay.')
            if instance.state in ('active', 'complete', 'failed') and pid not in instance.withdrawn:
                actions.append({'key': 'w', 'label': 'withdraw'})
            return detail, actions
        if selected and panel.handler:
            offer = owner.offer(selected, pid, panel.handler)
            job, person = owner.state.engine.templates[offer.template], owner.participant(pid)
            detail = ['Your solo reward: '+payment(offer.reward.scaled(1, False, person.archetype == 'operator')),
                'Next: '+(job.stages[0].label or job.stages[0].verb),
                'Route: '+job.approach_label,
                'Grade: '+str(job.min_grade)+'. '+('Story; no overall deadline.' if job.story else 'Generated; 60 min after acceptance.'),
                'Cost: no acceptance fee. Actions and hazards appear on the objective card.']
            detail += consequences(job)
            missing = owner.requirements(pid, job, broker=panel.handler == 'vesper')
            if job.story and panel.handler == 'vesper' and job.giver != 'vesper':
                detail += ['Neutral referral: giver standing is waived. Other prerequisites remain.',
                           'Completed work may return here; faction rewards retain their original owner.']
            if missing:
                detail += ['Requires: '+', '.join(describe_requirement(condition, owner.content) for condition in missing)]
            else:
                actions += [{'key': 'a', 'label': 'solo'}, {'key': 'c', 'label': 'crew'}]
            if job.approaches and not missing:
                actions += [{'key': str(i), 'label': approach.label} for i, approach in enumerate(job.approaches, 1)]
            return detail, actions
        return ['Visit a hall or the Tin Halo contract board for offers.',
                'Accepted jobs and crew proposals appear here.'], actions

    def body(self, session: Session, panel: Panel) -> dict[str, Any]:
        rows = self.rows(session, panel)
        if not rows:
            rows = [{'id': '', 'cells': ['No records yet']}]
        panel.cursor = max(0, min(panel.cursor, len(rows)-1))
        selected = rows[panel.cursor]['id'] if rows else ''
        card_target = panel.confirmation[1] if panel.confirmation else selected
        detail, actions = self.card(session, panel, card_target)
        if panel.confirmation:
            verb, target, option = panel.confirmation
            detail = ['Commit '+verb+'? Your chosen terms:'] + detail
            if verb == 'withdraw':
                instance = self.owner.state.engine.instances[target]
                detail.insert(1, 'Withdrawal is final for this reservation; disconnect keeps its deadline.' if instance.service
                    else 'You can resume original terms with R. Withdrawal clears your participation credit.')
            if verb == 'turn-in' and option:
                instance = self.owner.state.engine.instances[target]
                terms = instance.options[option]
                person = next(p for p in instance.roster if p.player == session.player_id)
                detail = [terms['label'], 'Your reward: '+payment(self.owner.state.engine.quote(instance, person, option)),
                          'Publication scope: '+terms['audience']]
                if terms.get('permit'):
                    permit = terms['permit']
                    detail.append(f"Effect: {permit['kind']} at {permit['target']} for {permit['expiry_seconds']} s.")
                detail += ['This choice is personal and cannot be reversed.', 'The other publication option will close.']
            actions = [{'key': 'y', 'label': 'confirm'}]
        width = 66 if session.caps['width'] < 100 else 50
        lines = [line for paragraph in detail for line in (textwrap.wrap(paragraph, width) or [''])]
        count = max(1, min(20 if session.caps['height'] == 24 else session.caps['height']-6,
                           session.caps['height']-4-min(8, 3+(session.caps['height']-24)*5//16))-6)
        if session.caps['width'] >= 100:
            count += 3
        pages = max(1, ceil(len(lines)/count))
        panel.page = min(panel.page, pages-1)
        if pages > 1:
            actions += [{'key': '[', 'label': 'previous'}, {'key': ']', 'label': 'more'}]
        body = menu('CONTRACTS / '+panel.tab.upper(), rows, panel.cursor,
                    '\n'.join(lines[panel.page*count:(panel.page+1)*count]), 'Esc/B returns; the world continues.')
        body.update(kind='contracts', actions=actions, page=panel.page+1, pages=pages,
                    columns=[f'Choice {panel.cursor+1 if rows else 0}/{len(rows)}; detail {panel.page+1}/{pages}'])
        return body

    def act(self, session: Session, panel: Panel, key: str, selected: str) -> None:
        owner, pid = self.owner, session.player_id
        if key in ('[', ']'):
            panel.page = max(0, panel.page + (1 if key == ']' else -1))
            return
        if panel.confirmation:
            verb, target, option = panel.confirmation
            if key != 'y':
                return
            if verb == 'turn-in':
                if not takes_turnin(self.station(session, panel.target), owner.state.engine.instances[target]):
                    raise ValueError('Return to the listed handler first.')
                owner.claim(target, pid, option or None)
            elif verb == 'start':
                owner.consent(target, pid)
                owner.start(target, pid)
            elif verb in ('withdraw', 'retry'):
                if owner.commerce.pending:
                    raise ValueError('The city is busy. Try again.')
                draft = owner.state.fork()
                if verb == 'withdraw':
                    owner.withdraw(draft, target, pid)
                else:
                    owner.retry(draft, target, pid)
                owner.write(draft)
            panel.confirmation = None
            return
        if key == 'v' and panel.handler:
            self.station(session, panel.target)
            obj = owner.commerce.nearby(session, panel.target)
            if not obj.spec.params.get('trade_counter') or not obj.spec.params.get('vendor'):
                raise ValueError('That board has no trade counter.')
            self.close(session)
            owner.commerce.menus[session.id] = CommerceMenu('vendor', obj.spec.id, opened=owner.clock.now_tick())
        elif key == 'j':
            panel.tab = 'jobs' if panel.tab == 'journal' else 'journal'
            panel.cursor, panel.page, panel.prose = 0, 0, False
        elif key == 'd' and panel.tab != 'journal':
            panel.tab = 'jobs' if panel.tab == 'done' else 'done'
            panel.cursor, panel.page = 0, 0
        elif key == 'p' and panel.tab == 'journal':
            panel.prose, panel.page = not panel.prose, 0
        elif selected.startswith('service:') and selected[8:] in owner.state.services.nodes:
            sid = selected[8:]
            crew = owner.game.crews.registry.crew_of(pid)
            roster = (pid,) if key in ('1', '2') or not crew else (pid, *(p for p in crew.members if p != pid))
            proposal = owner.propose_service(pid, sid, 'common' if key in ('1', '3') else 'reserve', roster)
            owner.consent(proposal.id, pid)
            if len(roster) == 1:
                panel.confirmation = ('start', proposal.id, '')
            else:
                for member in roster:
                    owner.log(member, 'Work-order proposal ready. Q shows the allocation; A accepts.')
            panel.cursor, panel.page = 0, 0
        elif selected in owner.proposals:
            if key == 'a':
                owner.consent(selected, pid)
            elif key == 's':
                panel.confirmation = ('start', selected, '')
        elif selected in owner.state.engine.instances:
            instance = owner.state.engine.instances[selected]
            if key == 't':
                panel.confirmation = ('turn-in', selected, '')
            elif key.isdigit() and instance.options:
                panel.confirmation = ('turn-in', selected, list(instance.options)[int(key)-1])
            elif key in ('w', 'r'):
                panel.confirmation = ('withdraw' if key == 'w' else 'retry', selected, '')
        elif selected and panel.handler:
            offer = owner.offer(selected, pid, panel.handler)
            job = owner.state.engine.templates[offer.template]
            crew = owner.game.crews.registry.crew_of(pid)
            roster = (pid,) if key != 'c' or not crew else (pid, *(p for p in crew.members if p != pid))
            approach = job.approaches[int(key)-1].id if key.isdigit() else 'default'
            proposal = owner.propose(pid, offer, roster, approach,
                                     broker='vesper' if panel.handler == 'vesper' and job.story else '')
            owner.consent(proposal.id, pid)
            if len(roster) == 1:
                panel.confirmation = ('start', proposal.id, '')
            else:
                for member in roster:
                    owner.log(member, 'Contract proposal ready. Q opens its terms; A accepts.')
            panel.cursor, panel.page = 0, 0

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        owner = self.owner
        if session.player_id not in self.game.players:
            return False
        name = frame.data.get('name', '') if frame.type == 'intent' else ''
        args = frame.data.get('args', {})
        key = frame.data.get('k', '') if frame.type == 'key' else ''
        panel = self.menus.get(session.id)
        try:
            if panel:
                if name == 'menu_close' or key.lower() in ('escape', 'b'):
                    if panel.confirmation:
                        verb, target, _ = panel.confirmation
                        proposal = owner.proposals.get(target)
                        if verb == 'start' and proposal and proposal.roster == (session.player_id,):
                            owner.proposals.pop(target)
                        panel.confirmation = None
                    elif panel.prose:
                        panel.prose, panel.page = False, 0
                    else:
                        self.close(session)
                    return True
                if name == 'menu_cursor' and type(args.get('delta')) is int and not panel.confirmation:
                    panel.cursor, panel.page, panel.prose = max(0, panel.cursor+args['delta']), 0, False
                    return True
                if name == 'menu_select' or key:
                    body = self.body(session, panel)
                    row = body['rows'][panel.cursor]['id'] if body['rows'] else ''
                    action = str(args.get('key', '')).lower() if name == 'menu_select' else key.lower()
                    if name == 'menu_select':
                        request = frame.data.get('request_id', '')
                        if (not request or request in self.requests.get(session.id, [])
                                or frame.data.get('expected_revision') != session.view_revision or args.get('row') != row):
                            return True
                        self.requests.setdefault(session.id, []).append(request)
                        self.requests[session.id] = self.requests[session.id][-128:]
                    if action in {a['key'] for a in body['actions']}:
                        self.act(session, panel, action, row)
                return True
            if session.pending_prompts or session.id in self.game.screens or session.id in self.sim.maps:
                return False
            if session.id in self.sim.external_views and not owner.lat.location(session):
                return False
            if name in ('journal.open', 'contracts.open') or key.lower() == 'q':
                target = args.get('target', '')
                handler = self.station(session, target) if target else ''
                self.menus[session.id] = Panel(tick, target, handler, 'journal' if name == 'journal.open' else 'jobs')
                return True
            if (name == 'interact' or key.lower() == 'e') and owner.commerce.ready(session):
                actor = self.game.combat.actor(self.game.players[session.player_id])
                objects = sorted((obj for obj in self.world_objects(actor)
                    if obj.spec.params.get('contract_handler')), key=lambda obj: obj.spec.id)
                if objects:
                    target = objects[0].spec.id
                    self.menus[session.id] = Panel(tick, target, self.station(session, target))
                    return True
        except (ValueError, KeyError, TypeError) as exc:
            owner.commerce.toast(session, str(exc) if isinstance(exc, ValueError) else 'That contract changed. Read its current card.')
            return True
        return False

    def world_objects(self, actor: Any) -> list[Any]:
        return [obj for obj in self.owner.world.zones[actor.zone].objects.values()
                if max(abs(obj.spec.tile[0]-actor.x), abs(obj.spec.tile[1]-actor.y)) <= 1]

    def tick(self, tick: int) -> None:
        for sid, panel in tuple(self.menus.items()):
            session = self.game.sessions.active.get(sid)
            if not session or session.player_id not in self.game.players:
                self.menus.pop(sid, None)
                self.sim.external_views.pop(sid, None)
                continue
            actor = self.game.combat.actor(self.game.players[session.player_id])
            if actor and tick-panel.opened >= MENU_TIMEOUT_SECONDS*TICK_HZ and self.owner.world.zones[actor.zone].allows_hostile(actor.position):
                self.close(session)
                continue
            try:
                self.sim.external_views[sid] = 'menu', self.body(session, panel)
            except (ValueError, KeyError):
                self.close(session)
        self.requests = {sid: rows for sid, rows in self.requests.items() if sid in self.game.sessions.active}
