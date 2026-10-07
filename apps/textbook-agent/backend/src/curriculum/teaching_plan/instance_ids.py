"""Unique skeleton slot instance identities."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence


def assign_slot_instance_ids(slot_roles: Sequence[str]) -> list[str]:
    """Map pedagogical slot roles to unique occurrence ids.

    Repeated apply/guided roles become ``apply-1``, ``apply-2``, … A single
    occurrence still gets a ``-1`` suffix so dictionaries are never keyed only
    by role when the same role can appear more than once across variants.
    """
    counts: dict[str, int] = {}
    totals: dict[str, int] = {}
    for role in slot_roles:
        totals[role] = totals.get(role, 0) + 1
    instance_ids: list[str] = []
    for role in slot_roles:
        counts[role] = counts.get(role, 0) + 1
        if totals[role] == 1:
            # Keep stable single-occurrence ids as the role itself for existing
            # packets that already use orient/explain/check without suffixes.
            instance_ids.append(role)
        else:
            instance_ids.append(f"{role}-{counts[role]}")
    return instance_ids


def role_from_instance_id(instance_id: str) -> str:
    """Recover the pedagogical role from an instance id."""
    if "-" not in instance_id:
        return instance_id
    head, _, tail = instance_id.rpartition("-")
    if tail.isdigit() and head:
        return head
    return instance_id


def catalog_slot_key(catalog_slots: Mapping[str, object], slot_id: str) -> str:
    """Key of the catalogue slot definition for a slot instance id.

    An id that is itself a catalogue slot wins; otherwise a repeated-slot
    instance id (``confront-2``) resolves to its role (``confront``).
    """
    if slot_id in catalog_slots:
        return slot_id
    role = role_from_instance_id(slot_id)
    return role if role in catalog_slots else slot_id


def normalize_slot_instance_ids(slot_ids: Iterable[str]) -> list[str]:
    """Make slot ids unique without rejecting repeats.

    Repeated slots of one type are legitimate. The first occurrence keeps its
    id; later ones become ``<id>-2``, ``<id>-3`` … in order (skipping any id
    already taken). Already-unique input is returned unchanged.
    """
    ids = list(slot_ids)
    taken = set(ids)
    seen: set[str] = set()
    counts: dict[str, int] = {}
    out: list[str] = []
    for item in ids:
        if item not in seen:
            seen.add(item)
            out.append(item)
            continue
        n = counts.get(item, 1)
        candidate = f"{item}-{n + 1}"
        while candidate in taken:
            n += 1
            candidate = f"{item}-{n + 1}"
        counts[item] = n + 1
        taken.add(candidate)
        seen.add(candidate)
        out.append(candidate)
    return out


def assert_unique_instance_ids(instance_ids: Iterable[str]) -> None:
    seen: set[str] = set()
    for item in instance_ids:
        if item in seen:
            raise ValueError(f"duplicate slot instance id {item!r}")
        seen.add(item)
