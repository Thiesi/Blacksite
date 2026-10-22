"""UI 4: server-built character and skills menus with readable row details."""

from collections.abc import Mapping
from dataclasses import dataclass
from math import ceil
import textwrap
from typing import Any

from blacksite.content.loader import ContentTree
from blacksite.server.implants import SLOTS, tolerance_used
from blacksite.server.inventory import Inventory
from blacksite.server.items import ItemInstance
from blacksite.server.modifiers import Modifiers, collect
from blacksite.server.players import Player
from blacksite.server.rules import character
from blacksite.server.skills import LINE_GROUP
from blacksite.server.wake import menu


@dataclass(frozen=True)
class Row:
    id: str
    label: str
    value: str
    detail: str


def build(title: str, rows: list[Row], cursor: int,
          actions: list[dict[str, str]]) -> dict[str, Any]:
    cursor = max(0, min(cursor, len(rows)-1))
    selected = rows[cursor]
    # The 132-column split pane is narrower than the 80-column detail
    # pane. Four lines fit both; put the selected row's facts first.
    detail = "\n".join(line for paragraph in selected.detail.split("\n")
                       for line in textwrap.wrap(paragraph, 52))
    return {**menu(title, [{"id": row.id, "cells": [row.label, row.value]} for row in rows],
                    cursor, detail), "columns": ["Record", "Value"], "actions": actions}


def bar(value: float) -> str:
    filled = max(0, min(10, int(value//10)))
    return "["+"#"*filled+"."*(10-filled)+"]"


def skill_menu(player: Player, content: ContentTree, cursor: int, now: float) -> dict[str, Any]:
    from datetime import datetime, timezone
    day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
    ledger = player.progress.get("skill_use", {})
    points = player.progress.get("points", 0)
    rows = []
    for line, attribute in LINE_GROUP.items():
        value = float(player.skills.get(line, 0))
        definition = content.skills.get(line)
        name = definition.name if definition else line.title()
        used = ledger.get("gains", {}).get(line, 0) if ledger.get("day") == day else 0
        detail = (f"{name}: {value:g}/100. {points} grade points available.\n"
                  f"Use gain today {used:g}/2; spending is separate.\n"
                  f"One point buys up to 1 skill, capped at 100.\n"
                  f"10 permanent group points raise {attribute.title()} by 1.")
        rows.append(Row(line, name, f"{value:g} {bar(value)}", detail))
    return build("SKILLS - "+player.name, rows, cursor,
                 [{"key": "+", "label": "spend 1 grade point"}])


def character_sheet(player: Player, content: ContentTree,
                    items: Mapping[str, ItemInstance], now: float,
                    lease_days: int, cursor: int = 0,
                    modifiers: Modifiers | None = None,
                    surge_preview: str | None = None) -> dict[str, Any]:
    mods = modifiers or collect(player, items, content.items, now)
    grade = next((g for g in content.grades.values() if g.grade == player.grade), None)
    title = grade.title if grade else character.grade_name(player.grade)
    next_xp = character.grade_threshold(player.grade+1) if player.grade < 30 else None
    rows = [Row("archetype", "Archetype", player.archetype.title(), f"BBS handle: {player.bbs_handle}"),
        Row("grade", "Grade", f"{player.grade} {title}",
                f"Grade {player.grade}: {title}.\nEach gained grade adds 3 points and 1 Vitals.\nPersonhood stays once discharged."),
        Row("xp", "XP", str(player.xp), f"{max(0, next_xp-player.xp)} XP to grade {player.grade+1}." if next_xp else "You reach the maximum grade, 30."),
        Row("points", "Grade points", str(player.progress.get("points", 0)), "S opens skills. Select a line and press + to spend.\nSpending has no daily use-gain cap."),
        Row("health", "Health", f"{player.health}/{mods.health_max(player)}", "Installed and active health modifiers are included.\nA grade gain preserves your current health ratio."),
        Row("stamina", "Stamina", f"{player.stamina}/{character.stamina_max(mods.attribute(player, 'nerve'), mods.attribute(player, 'frame'))}", "Nerve and Frame determine your stamina pool."),
        Row("carry", "Carry kg", f"{Inventory(dict(items), content.items).weight(player):g}/{character.carry_kg(mods.attribute(player, 'frame'))+mods.bonus('carry_kg'):g}", "Carried mass / current capacity.\nAbove capacity your walk and sprint take twice as long."),
        Row("tolerance", "Tolerance", f"{tolerance_used(player, items, content.items)}/{mods.tolerance(player)}", "Installed tolerance used / current capacity.\nChrome adds one temporarily; expiry may unseat hardware."),
        Row("identity", "Personhood", "Discharged" if player.legal_at else "Under lease", f"Elapsed lease: {lease_days}/90 days.\nEarly discharge: {player.xp}/1500 XP, grade 5.\nPvP grade protection is separate from personhood."),
        Row("hand", "Hand chits", str(player.chits_hand), "Carried chits pay ordinary counters and surgery."),
        Row("bank", "Bank chits", str(player.chits_bank), "Banked chits remain separate from carried money.")]
    gear_evasion = sum(content.items[items[iid].template].armour.evasion
        for iid in set(player.equipment.values()) if iid in items
        and content.items[items[iid].template].armour)
    rows.append(Row("evasion", "Evasion", f"{mods.attribute(player, 'nerve')/3+mods.bonus('evasion')+gear_evasion:g}",
                    "Nerve / 3 plus equipment.\nCover is separate and is not counted twice."))
    base = character.attributes(player.archetype)
    for name, permanent in player.attributes.items():
        effective = mods.attribute(player, name)
        rows.append(Row("attribute:"+name, name.title(), str(effective),
            f"Base {base[name]}; permanent gain {permanent-base[name]:+d}; temporary {effective-permanent:+d}.\n"
            +("Vitals rises through grades and implants." if name == "vitals" else "Only permanent skills raise attribute groups.")))
    for line in LINE_GROUP:
        value = float(player.skills.get(line, 0))
        rows.append(Row("skill:"+line, line.title(), f"{value:g} {bar(value)}",
            f"Permanent {line.title()} {value:g}/100.\nS opens the skills menu; + spends one grade point there."))
    for slot in SLOTS:
        item = items.get(player.implants.get(slot, ""))
        template = content.items.get(item.template) if item else None
        name = template.name if template else "Native rig" if slot == "rig" and player.archetype == "ghost" else "Empty"
        detail = (f"{slot.title()}: {name}.\nTolerance {template.implant.tolerance}; quality {item.quality:g}."
                  if template and template.implant else f"{slot.title()}: {name}.")
        if template and template.implant and template.implant.effects.get("surge_inspect"):
            detail += "\n"+(surge_preview or "No effect yet: Surge forecasts are not available.")
        rows.append(Row("implant:"+slot, slot.title(), name, detail))
    dependent = {d["template"] for d in player.dependencies}
    for state in player.drugs_active:
        template = content.items.get(state["template"])
        if not template or now >= state["crash_until"]:
            continue
        positive = now < state["effect_until"]
        phase, until = ("Effect", state["effect_until"]) if positive else ("Crash", state["crash_until"])
        detail = f"{template.name}: {phase.lower()} {ceil(until-now)}s remaining."
        if template.id in dependent:
            detail += "\nDependency withdrawal also applies until detox."
        rows.append(Row("substance:"+template.id, template.name, phase, detail))
    for tid in sorted(dependent):
        name = content.items[tid].name if tid in content.items else "Unknown substance"
        rows.append(Row("dependency:"+tid, name, "Dependency", "Withdrawal persists until detox.\nSablier: 400 chits, 10 minutes; logging out is safe."))
    detox = player.progress.get("detox")
    if detox and now < detox["until"]:
        rows.append(Row("detox", "Detox", f"{ceil(detox['until']-now)}s", "Treatment blocks actions in the clinic pocket.\nLogging out does not restart or extend treatment."))
    return build("CHARACTER - "+player.name, rows, cursor,
                 [{"key": "s", "label": "skills"}, {"key": "d", "label": "delete character"}])
