"""Step and Room registries."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from my_coding_team.core.room import Room
    from my_coding_team.core.step import Step


STEPS: dict[str, "Step"] = {}
ROOMS: dict[str, "Room"] = {}


def register_step(step: "Step") -> "Step":
    """Register a Step by name."""
    STEPS[step.name] = step
    return step


def register_room(room: "Room") -> "Room":
    """Register a Room by name."""
    ROOMS[room.name] = room
    return room
