"""Observed economic receipts with explicitly assumed activity schedules.

Development harness only. Positions, completed NPC defeats and cleared ICE
isolate receipt accounting; they do not measure combat, travel or fun.
No fixture funds are added. Initial equipment/principal is never sold.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
import json
from pathlib import Path
from typing import Any

from blacksite.content.loader import load_content
from blacksite.server.clinics import Operation
from blacksite.server.npcs.templates import make_actor
from blacksite.server.protocol import Frame
from tests.character_helpers import act, create, place
from tests.harness import HeadlessServer
from scripts.report_s16_progression import report as progression_report


def setup(size: int = 1) -> tuple[Any, ...]:
    content = load_content(Path(__file__).parents[1]/'src/blacksite/content')
    content.zones = {k:replace(z,meta=replace(z.meta,spawners=())) for k,z in content.zones.items()}
    game = HeadlessServer(content,character_state={})
    clients,players = [],[]
    for index in range(size):
        client = game.connect({'user_id':index+1,'handle':f'Earning{index}','node_name':'receipt-fixture'})
        create(game,client,archetype=1 if index == 0 else 3,name=f'Earning{index}',card='none')
        player = game.core.characters.players[client.session.player_id]
        player.progress['wake_combat'] = 'skipped'
        clients.append(client)
        players.append(player)
    if size > 1:
        crews = game.core.crews
        for index in range(1,size):
            crews.perform(clients[0].session,'invite',players[index].id)
            invitation = next(i for i in crews.registry.invites.values() if i.target == players[index].id)
            crews.perform(clients[index].session,'accept',invitation.id)
    return game,game.core.contracts,clients,players


def locate(game: Any, client: Any, zone: str, origin: tuple[int,int]) -> None:
    actor = game.core.characters.sim.avatars[client.session.user_id].actor
    tile = game.core.world.free_tile(zone,origin,actor)
    place(game,client,zone,tile)


def contract_receipt(size: int) -> dict[str,Any]:
    game,owner,clients,players = setup(size)
    clear = next(o for o in owner.state.engine.board('wardens',owner.now())
                 if owner.state.engine.templates[o.template].type == 'clear')
    anchor = owner.world.zones['terraces-blocks'].objects['letting-office'].spec.tile
    for client in clients:
        locate(game,client,'terraces-blocks',anchor)
    proposal = owner.propose(players[0].id,clear,tuple(p.id for p in players))
    for player in players:
        owner.consent(proposal.id,player.id)
    owner.start(proposal.id,players[0].id)
    game.commit_commerce()
    instance = next(j for j in owner.state.engine.instances.values() if j.offer == clear.id)
    owner.scenes.reconcile()
    actors = [a for a in owner.world.actors.values() if a.behaviour.get('mission') == instance.id]
    before = [p.chits_hand for p in players]
    for index,actor in enumerate(actors):
        source = game.core.combat.actor(players[index % size])
        actor.health = 0  # Explicit completed-defeat fixture, not combat pacing.
        game.core.npcs.died(source,actor)
        game.commit_commerce()
    assert owner.state.engine.instances[instance.id].state == 'complete'
    xp = [p.xp for p in players]
    owner.claim(instance.id,players[0].id)
    game.commit_commerce()
    paid = [dict(archetype=p.archetype,chits=p.chits_hand-before[i],xp=p.xp-xp[i])
            for i,p in enumerate(players)]
    assert all(p['chits'] > 0 for p in paid)
    balances = [p.chits_hand for p in players]
    owner.claim(instance.id,players[0].id)
    game.commit_commerce()
    assert balances == [p.chits_hand for p in players]
    return dict(template=instance.template,roster=size,required_defeats=len(actors),
                paid=paid,duplicate_credit=0)


def street_receipts(defeats: int = 20) -> dict[str,Any]:
    game,owner,clients,players = setup()
    client,player = clients[0],players[0]
    locate(game,client,'terraces-blocks',(30,5))
    source = game.core.combat.actor(player)
    start,loot = player.chits_hand,Counter()
    for index in range(defeats):
        tile = owner.world.free_tile(source.zone,(source.x+2,source.y))
        actor = make_actor(owner.content.npcs['npc-sable-enforcer'],f'economy-enforcer-{index}',{})
        owner.world.enter(actor,source.zone,tile)
        actor.health = 0
        game.core.npcs.died(source,actor)
        game.commit_commerce()
        cache_id = 'npc-cache:'+actor.id
        cache = owner.commerce.caches.get(cache_id)
        for iid in list(cache['items']) if cache else ():
            item = owner.commerce.items[iid]
            template,count = item.template,item.stack
            locate(game,client,cache['zone'],tuple(cache['tile']))
            owner.commerce.propose(client.session,'inv.pickup',{'target':cache_id,'item':iid})
            game.commit_commerce()
            loot[template] += count
            locate(game,client,'vatside-wake-hall',(34,15))
            owned = next(owner.commerce.items[key] for key in player.inventory
                         if owner.commerce.items[key].template == template and not owner.commerce.items[key].secured)
            game.clock.advance(11)  # Respect the real one-trade/second gate.
            owner.commerce.propose(client.session,'vendor.sell',
                                   {'target':'wake-outfitter','item':owned.id,'qty':count})
            game.commit_commerce()
        locate(game,client,'terraces-blocks',(30,5))
    earned = player.chits_hand-start
    spent = sum(v.spent for v in owner.commerce.budgets.values())
    assert earned == spent
    return dict(npc='npc-sable-enforcer',defeats=defeats,loot=dict(loot),
                sold_chits=earned,vendor_budget_spent=spent,starting_principal_sold=0)


def core_receipt() -> dict[str,Any]:
    game,owner,clients,players = setup()
    client,player = clients[0],players[0]
    place(game,client,'core-plaza',(30,5))
    act(game,client,Frame('key',{'k':'j','t':0}))
    game.commit_commerce()
    presence = owner.lat.presences[player.id]
    presence.cell = next(c.id for c in owner.lat.sectors.records[presence.sector].cells
                         if c.core_id == 'lat-civic-ledger')
    owner.lat.encounters.enter(client.session,'lat-civic-ledger')
    instance = owner.lat.encounters.core(presence)
    presence.room = 'r-cache'  # Explicit navigation/ICE isolation.
    for ice in instance.ice.values():
        ice.integrity = 0
    data = next(d for d in instance.graph.room(presence.room).data if d.kind == 'chits')
    key = owner.lat.encounters.source(presence,data)
    available = owner.lat.sources.refresh(key,data,game.clock.now_tick())
    before = player.chits_hand
    owner.lat.encounters.start_lift(presence,data.id,available.generation)
    game.step(presence.procedure.until-game.clock.now_tick())
    game.commit_commerce()
    return dict(core='lat-civic-ledger',data=data.id,chits=player.chits_hand-before,
                tier=owner.content.cores['lat-civic-ledger'].tier)


def prices() -> dict[str,Any]:
    game,owner,clients,players = setup()
    player = players[0]
    clinic = owner.progression.clinics
    catalog = {}
    for iid in ('wpn_kestrel_sidearm','wpn_halvard_hv7','imp_halvard_reflex_arm','imp_rig_ow_jury','imp_rig_sablier_clinical'):
        item = owner.content.items[iid]
        entry: dict[str,Any] = dict(name=item.name,list_price=item.base_price)
        if item.implant:
            slot = 'arms1' if item.implant.slot == 'arms' else item.implant.slot
            for kind in ('sablier','black'):
                try:
                    vendor = next(v for v in owner.content.vendors.values() if v.clinic == kind)
                    quote = clinic.quote(player,vendor,Operation('report','install',iid,slot))
                    entry[kind] = asdict(quote)|{'total':quote.total}
                except ValueError as exc:
                    entry[kind] = {'locked':str(exc)}
        catalog[iid] = entry
    detox = clinic.quote(player,owner.content.vendors['sablier-clinic'],Operation('detox','detox'))
    catalog['detox'] = dict(name='Detox',total=detox.total)
    vendor = owner.content.vendors['vesper']
    programs = {s.item:owner.commerce.quote(player,vendor,s,1) for s in owner.commerce.stock(vendor)
                if s.item in ('prg_lance','prg_bunker','prg_signet','prg_anchor')}
    return dict(catalog=catalog,programs=programs,initial_cash=player.chits_hand,content_hash=owner.content.hash)


def forecast(cost: int, initial: int, *, job: int = 0, lift: int = 0,
             loot_per_hour: float = 0, defeats_per_hour: int = 0) -> int | None:
    """Gross cash on discrete assumed outcomes; each goal starts afresh."""
    if initial >= cost:
        return 0
    balance = float(initial)
    # A bounded ten-day forecast also covers the very poor ammo-sale loop.
    for minute in range(1,10*24*60+1):
        if minute % 15 == 0:
            balance += job
        if minute % 10 == 0:
            balance += lift
        # The twenty-defeat sample is prorated at the declared cadence.
        balance += loot_per_hour*defeats_per_hour/20/60
        if balance >= cost:
            return minute
    return None


def report() -> dict[str,Any]:
    solo,crew = contract_receipt(1),contract_receipt(2)
    street,core,costs = street_receipts(),core_receipt(),prices()
    # This cadence is an explicit scenario, not an observed play session.
    # Four jobs/hour is below one board's ten offers/hour. Six successful
    # core lifts/hour assume a route across respawned sources.
    profiles = dict(street=dict(loot_per_hour=street['sold_chits'],defeats_per_hour=20),
        solo_jobs=dict(job=solo['paid'][0]['chits']),
        crew_jobs_ghost=dict(job=crew['paid'][0]['chits']),
        crew_jobs_operator=dict(job=crew['paid'][1]['chits']),
        mixed_solo=dict(job=solo['paid'][0]['chits'],lift=core['chits'],
                        loot_per_hour=street['sold_chits'],defeats_per_hour=8),
        mixed_crew_lifter=dict(job=crew['paid'][0]['chits'],lift=core['chits'],
                               loot_per_hour=street['sold_chits'],defeats_per_hour=8),
        mixed_crew_support=dict(job=crew['paid'][1]['chits']))
    rates = {name:4*p.get('job',0)+6*p.get('lift',0)+p.get('loot_per_hour',0)*p.get('defeats_per_hour',0)/20
             for name,p in profiles.items()}
    affordability = {}
    for id,row in costs['catalog'].items():
        total = row.get('sablier',{}).get('total',row.get('total',row.get('list_price',0)))
        affordability[id] = {name:forecast(total,costs['initial_cash'],**profile) for name,profile in profiles.items()}
    for id,total in costs['programs'].items():
        affordability[id] = {name:forecast(total,costs['initial_cash'],**profile) for name,profile in profiles.items()}
    fee = costs['catalog']['imp_halvard_reflex_arm']['sablier']['service_price']
    affordability['owned_reflex_arm_installation_only'] = {
        name:forecast(fee,costs['initial_cash'],**profile) for name,profile in profiles.items()}
    return dict(kind='observed receipt amounts; assumed cadence; gross affordability forecast',
        fixtures=['suppressed public NPC spawners','direct legal position setup','completed-defeat injection',
                  'cleared ICE and direct core room placement'],
        unmeasured=['travel and combat difficulty','ammo, healing, rent, failures and other expenses',
                    'S25 source availability','human enjoyment and full-city pacing'],
        distribution='Core cash and corpse loot go to their recipient, not every crew member. Support has contract income only. No equal-split cash transfer is assumed.',
        prices_note='Catalog/clinic quotes do not create missing S25 shop or clinic placements. Each forecast is a separate purchase from the original 200 chits.',
        forecast_horizon_minutes=10*24*60,
        xp_note='S16 assumed discovery/run schedules plus four observed-contract-XP grants per hour and grade-one street opponents. Mission-defeat XP is omitted; activity cadence is not measured.',
        cadence=dict(jobs_per_hour=4,lifts_per_hour=6,street_defeats_per_hour=20,mixed_defeats_per_hour=8),
        receipts=dict(solo=solo,crew=crew,street=street,core=core),prices=costs,
        gross_chits_per_hour=rates,gross_minutes_to_afford_from_starting_cash=affordability,
        progression_schedules={name:progression_report('street' if name == 'street' else 'mixed',
            contract_xp=xp,opponent_grade=1) for name,xp in
            (('street',0),('mixed_solo',solo['paid'][0]['xp']),('mixed_crew',crew['paid'][0]['xp']))})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    result = json.dumps(report(),indent=2)+'\n'
    if args.output:
        args.output.write_text(result,encoding='utf-8',newline='\n')
    else:
        print(result,end='')
