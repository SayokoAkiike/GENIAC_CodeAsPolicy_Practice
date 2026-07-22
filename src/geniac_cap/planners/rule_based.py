"""A rule-based Planner that works without any external LLM API.

Design notes:
  * It recognizes a family of "transport" verbs in Japanese and English
    (e.g. 運ぶ/置く/移動する/移す/carry/move/place) rather than a single fixed
    phrase, so it generalizes across the sample task set instead of being a
    one-task-only if/else chain.
  * Object and location names are matched against the PlanningContext using
    (a) the literal name with underscores turned into spaces (covers English
    instructions like "the red block"), and (b) a small synonym table for
    common Japanese phrases used in the bundled sample tasks. The synonym
    table is easy to extend as more tasks are added.
  * The source location for "pick" is looked up from
    context.object_locations (i.e. "where is the object right now"), and the
    destination is whichever known location is mentioned in the instruction
    that is *not* the source.
"""

from __future__ import annotations

import re

from geniac_cap.exceptions import PlanningError
from geniac_cap.models import Action, ActionName, ActionPlan
from geniac_cap.planners.base import BasePlanner, PlanningContext
from geniac_cap.utils.logging import get_logger

logger = get_logger(__name__)

# Verbs/phrases that indicate a "move this object somewhere" instruction.
_TRANSPORT_VERB_PATTERN = re.compile(
    "|".join(
        [
            "運んで", "運ぶ", "移して", "移す", "移動して", "移動する",
            "置いて", "置く", "入れて", "入れる",
            "carry", "move", "place", "put", "transfer",
        ]
    ),
    re.IGNORECASE,
)

# object_name -> extra Japanese/English surface forms to match in free text.
OBJECT_SYNONYMS: dict[str, list[str]] = {
    "red_block": ["赤いブロック", "赤ブロック", "red block"],
    "green_block": ["緑のブロック", "緑ブロック", "green block"],
    "cup": ["カップ", "コップ"],
    "bottle": ["ボトル"],
    "water_bottle": ["水のボトル", "水ボトル", "water bottle"],
    "towel": ["タオル"],
    "medicine_box": ["薬箱", "薬のケース", "medicine box"],
    "book": ["本"],
    "plate": ["皿", "お皿"],
    "notebook": ["ノート"],
}

# location_name -> extra Japanese surface forms.
LOCATION_SYNONYMS: dict[str, list[str]] = {
    "blue_shelf": ["青い棚", "青棚"],
    "tray": ["トレイ"],
    "table": ["テーブル", "机"],
    "desk": ["机"],
    "kitchen": ["キッチン", "台所"],
    "patient_room": ["患者室"],
    "bedside": ["ベッド横", "ベッドサイド", "ベッド脇"],
    "linen_closet": ["リネン庫", "リネンクローゼット"],
    "nurse_station": ["ナースステーション"],
    "storage_room": ["保管室", "物置"],
    "bookshelf": ["本棚"],
    "red_box": ["赤い箱", "赤箱"],
    "office": ["オフィス", "事務室"],
    "bathroom": ["浴室", "お風呂場"],
}


def _matches(name: str, synonyms: dict[str, list[str]], text: str) -> bool:
    """Return True if `name` (or any of its synonyms) appears in `text`."""

    surface_forms = [name.replace("_", " "), name] + synonyms.get(name, [])
    return any(form.lower() in text.lower() or form in text for form in surface_forms)


def _find_object(instruction: str, context: PlanningContext) -> str:
    candidates = [obj for obj in context.objects if _matches(obj, OBJECT_SYNONYMS, instruction)]
    if not candidates:
        raise PlanningError(f"Could not identify a known object in instruction: '{instruction}'")
    if len(candidates) > 1:
        logger.warning(
            "Multiple object candidates matched %s; using first: %s", candidates, candidates[0]
        )
    return candidates[0]


def _find_destination(instruction: str, context: PlanningContext, source_location: str) -> str:
    candidates = [
        loc
        for loc in context.locations
        if loc != source_location and _matches(loc, LOCATION_SYNONYMS, instruction)
    ]
    if not candidates:
        # Fall back to any mentioned location, even if it equals the source
        # (covers a no-op instruction) -- but prefer a genuine "other" location first.
        all_mentions = [
            loc for loc in context.locations if _matches(loc, LOCATION_SYNONYMS, instruction)
        ]
        if all_mentions:
            return all_mentions[0]
        raise PlanningError(
            f"Could not identify a destination location in instruction: '{instruction}'"
        )
    if len(candidates) > 1:
        logger.warning(
            "Multiple destination candidates matched %s; using first: %s", candidates, candidates[0]
        )
    return candidates[0]


class RuleBasedPlanner(BasePlanner):
    """Deterministic planner covering the "move object X to location Y" pattern.

    This is the default planner and requires no external API access.
    """

    name = "rule-based"

    def plan(self, instruction: str, context: PlanningContext) -> ActionPlan:
        if not _TRANSPORT_VERB_PATTERN.search(instruction):
            raise PlanningError(
                f"Instruction does not look like a supported transport command: '{instruction}'"
            )

        object_name = _find_object(instruction, context)
        source_location = context.object_locations.get(object_name)
        if source_location is None:
            raise PlanningError(f"Unknown current location for object '{object_name}'")

        destination = _find_destination(instruction, context, source_location)

        steps = [
            Action(action=ActionName.MOVE_TO, args={"location": source_location}),
            Action(action=ActionName.PICK, args={"object_name": object_name}),
            Action(action=ActionName.MOVE_TO, args={"location": destination}),
            Action(action=ActionName.PLACE, args={"target_location": destination}),
        ]
        logger.info("RuleBasedPlanner produced %d step(s) for: '%s'", len(steps), instruction)
        return ActionPlan(steps=steps)
