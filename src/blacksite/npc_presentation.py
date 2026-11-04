"""Shared template-only disclosure rules (architecture 5.5.4, entities 1.8)."""

from blacksite.content.schema import NpcTemplate


def npc_class(template: NpcTemplate | None, faction: str | None) -> str:
    if template and template.training:
        return 'drone'
    if faction == 'wardens':
        return 'warden'
    behaviours = {b.kind for b in template.behaviours} if template else set()
    if 'guard' in behaviours:
        return 'security'
    if template and (template.vendor or 'vendor' in behaviours or 'talker' in behaviours):
        return 'service'
    if template and any(b.params.get('hostile_all') for b in template.behaviours):
        return 'hostile'
    return 'civilian'


def cover_role(presented: str) -> str:
    return {'civilian': 'npc_neutral', 'warden': 'npc_warden',
            'security': 'npc_neutral', 'service': 'npc_vendor',
            'hostile': 'npc_hostile'}[presented]


def channels(template: NpcTemplate) -> dict[str, object]:
    """What an unrevealed NPC template exposes, excluding its hidden rules."""
    true = npc_class(template, template.faction)
    presented = (template.presents or true) if not template.training else true
    covered = presented != true
    kinds = tuple(b.kind for b in template.behaviours)
    return {'name': template.cover_name if covered else template.name,
            'class': presented,
            'colour_role': cover_role(presented) if covered else 'npc_'+(template.faction or 'neutral'),
            'behaviour_kinds': kinds,
            'anchored': any(bool(b.params.get('anchor')) for b in template.behaviours),
            'interactions': (bool(template.dialogue or 'talker' in kinds), template.vendor),
            'dialogue': template.dialogue}
