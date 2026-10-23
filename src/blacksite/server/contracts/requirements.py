"""Human-readable requirement labels shared by cards and refusal messages."""

from blacksite.content.loader import ContentTree


def describe(condition: str, content: ContentTree) -> str:
    name, *args = condition.split()
    if name in ('standing_at_least', 'standing_below'):
        faction = content.factions[args[0]].name
        return faction+' standing '+('at least ' if name.endswith('at_least') else 'below ')+args[1]
    if name in ('grade_at_least', 'grade_below'):
        return 'Grade '+('at least ' if name.endswith('at_least') else 'below ')+args[0]
    if name in ('member_of', 'not_member_of'):
        return ('join ' if name == 'member_of' else 'leave ')+content.factions[args[0]].name
    if name == 'archetype':
        return args[0].capitalize()+' training'
    if name == 'has_item':
        return 'carry '+content.items[args[0]].name
    if name == 'has_evidence':
        record = content.evidence[args[0]]
        return 'acquire evidence: '+record.observation
    if name in ('completed_contract', 'has_contract'):
        job = content.contracts.get(args[0])
        return ('complete ' if name == 'completed_contract' else 'accept ')+(job.name if job and job.name else args[0])
    if name == 'season_available':
        return 'Season '+args[0]+' available'
    if name == 'event_active':
        event = content.events.get(args[0])
        return 'active event: '+(event.name if event else args[0])
    if name == 'service_state':
        return content.services[args[0]].name+': '+args[1]
    if name == 'legal':
        return 'legal status'
    if name == 'not_legal':
        return 'not legally registered'
    return 'further story progress'
