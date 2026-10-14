"""Read players' saved state (inventory, armor, ender chest, stats) from a world.

Works on the files the server writes to <world>/playerdata/<uuid>.dat, so it
needs no plugin and works while the server is off. Handles both item formats:
  - 1.20.5+: {id, count, components: {...}}, armor in `equipment` since 1.21.5
  - older:   {id, Count, tag: {Enchantments, Damage, display: {Name}}},
             armor in Inventory slots 100-103 and offhand in slot -106
"""

import json
import os
import re

from utils import nbt

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# Vanilla max durability, for the durability bar (only overridden values are
# stored in the item itself).
_ARMOR = {"leather": (55, 80, 75, 65), "chainmail": (165, 240, 225, 195), "iron": (165, 240, 225, 195),
          "golden": (77, 112, 105, 91), "diamond": (363, 528, 495, 429), "netherite": (407, 592, 555, 481),
          "copper": (121, 176, 165, 143)}
_TOOLS = {"wooden": 59, "stone": 131, "copper": 190, "iron": 250, "golden": 32, "diamond": 1561, "netherite": 2031}
MAX_DAMAGE = {
    "bow": 384, "crossbow": 465, "trident": 250, "elytra": 432, "shield": 336, "fishing_rod": 64,
    "shears": 238, "flint_and_steel": 64, "mace": 500, "turtle_helmet": 275, "carrot_on_a_stick": 25,
    "warped_fungus_on_a_stick": 100, "brush": 64, "wolf_armor": 64,
}
for _mat, (_h, _c, _l, _b) in _ARMOR.items():
    MAX_DAMAGE.update({f"{_mat}_helmet": _h, f"{_mat}_chestplate": _c, f"{_mat}_leggings": _l, f"{_mat}_boots": _b})
for _mat, _d in _TOOLS.items():
    for _tool in ("sword", "pickaxe", "axe", "shovel", "hoe"):
        MAX_DAMAGE[f"{_mat}_{_tool}"] = _d

GAMEMODES = {0: "survival", 1: "creative", 2: "adventure", 3: "spectator"}
_EQUIP_SLOTS = ("head", "chest", "legs", "feet")


def short_id(item_id: str) -> str:
    return (item_id or "").split(":", 1)[-1]


def full_id(item_id: str) -> str:
    """Namespaced id; modded items keep their mod ("create:wrench")."""
    item_id = str(item_id or "").strip().lower()
    return item_id if ":" in item_id else f"minecraft:{item_id}"


def _text_of(value):
    """Plain text from a JSON text component, an NBT text compound or a string."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return value
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_text_of(v) or "" for v in value)
    if isinstance(value, dict):
        out = str(value.get("text", "") or value.get("translate", ""))
        for extra in value.get("extra", []) or []:
            out += _text_of(extra) or ""
        return out
    return str(value)


def _enchantments(components: dict, tag: dict, key_new: str, key_old: str):
    raw = components.get(key_new)
    out = []
    if isinstance(raw, dict):
        levels = raw.get("levels") if isinstance(raw.get("levels"), dict) else raw
        for ench, lvl in levels.items():
            if isinstance(lvl, int):
                out.append({"id": full_id(ench), "level": lvl})
    for e in (tag.get(key_old) or []):
        if isinstance(e, dict) and "id" in e:
            out.append({"id": full_id(e["id"]), "level": int(e.get("lvl", 1))})
    return out


def parse_item(raw: dict, slot=None):
    if not isinstance(raw, dict) or not raw.get("id"):
        return None
    item_id = full_id(raw["id"])
    if item_id == "minecraft:air":
        return None
    components = raw.get("components") or {}
    tag = raw.get("tag") or {}
    count = raw.get("count", raw.get("Count", 1))
    damage = components.get("minecraft:damage", tag.get("Damage"))
    max_damage = components.get("minecraft:max_damage") or (
        MAX_DAMAGE.get(short_id(item_id)) if item_id.startswith("minecraft:") else None)
    name = _text_of(components.get("minecraft:custom_name"))
    if name is None:
        name = _text_of((tag.get("display") or {}).get("Name"))
    enchants = _enchantments(components, tag, "minecraft:enchantments", "Enchantments")
    stored = _enchantments(components, tag, "minecraft:stored_enchantments", "StoredEnchantments")
    item = {"id": item_id, "count": int(count) if isinstance(count, (int, float)) else 1}
    if slot is not None:
        item["slot"] = slot
    if name:
        item["custom_name"] = name
    if enchants:
        item["enchantments"] = enchants
    if stored:
        item["stored_enchantments"] = stored
    if isinstance(damage, int) and damage > 0 and max_damage:
        item["durability"] = {"remaining": max(0, max_damage - damage), "max": int(max_damage)}
    return item


def parse_player(data: dict) -> dict:
    """Turn a player .dat compound into {inventory, armor, offhand, ender_chest, stats}."""
    inventory, armor, offhand = [], {}, None
    for raw in data.get("Inventory") or []:
        slot = raw.get("Slot")
        item = parse_item(raw, slot)
        if not item or slot is None:
            continue
        if 0 <= slot <= 35:
            inventory.append(item)
        elif 100 <= slot <= 103:  # pre-1.21.5 armor: 100 boots .. 103 helmet
            armor[_EQUIP_SLOTS[103 - slot]] = item
        elif slot == -106:
            offhand = item
    equipment = data.get("equipment") or {}
    for key in _EQUIP_SLOTS:
        item = parse_item(equipment.get(key))
        if item:
            armor[key] = item
    if equipment.get("offhand"):
        offhand = parse_item(equipment["offhand"]) or offhand

    ender = [i for i in (parse_item(r, r.get("Slot")) for r in data.get("EnderItems") or []) if i]

    pos = data.get("Pos") or []
    dim = data.get("Dimension")
    if isinstance(dim, int):  # very old worlds
        dim = {-1: "the_nether", 0: "overworld", 1: "the_end"}.get(dim, "overworld")
    stats = {
        "health": round(float(data.get("Health", 20)), 1),
        "food": int(data.get("foodLevel", 20)),
        "xp_level": int(data.get("XpLevel", 0)),
        "gamemode": GAMEMODES.get(data.get("playerGameType"), "survival"),
        "dimension": short_id(str(dim or "overworld")),
        "position": [round(float(p), 1) for p in pos[:3]] if len(pos) >= 3 else None,
        "selected_slot": int(data.get("SelectedItemSlot", 0)),
    }
    return {"inventory": inventory, "armor": armor, "offhand": offhand, "ender_chest": ender, "stats": stats}


def playerdata_dirs(server_path: str, world_name: str):
    """Folders holding <uuid>.dat files: Minecraft 26.x moved them from
    <world>/playerdata to <world>/players/data. Newest layout first."""
    world = os.path.join(server_path, world_name)
    return [d for d in (os.path.join(world, "players", "data"), os.path.join(world, "playerdata")) if os.path.isdir(d)]


def _player_file(server_path, world_name, uuid):
    for d in playerdata_dirs(server_path, world_name):
        path = os.path.join(d, f"{uuid}.dat")
        if os.path.exists(path):
            return path
    return None


def load_names(server_path: str) -> dict:
    """uuid -> name from the server's usercache.json (written by the server)."""
    names = {}
    try:
        with open(os.path.join(server_path, "usercache.json"), "r", encoding="utf-8") as f:
            for entry in json.load(f):
                if entry.get("uuid") and entry.get("name"):
                    names[entry["uuid"].lower()] = entry["name"]
    except (OSError, ValueError, TypeError):
        pass
    return names


def list_players(server_path: str, world_name: str):
    names = load_names(server_path)
    found = {}
    for folder in playerdata_dirs(server_path, world_name):
        try:
            entries = os.listdir(folder)
        except OSError:
            continue
        for fn in entries:
            uuid = fn[:-4].lower() if fn.endswith(".dat") else ""
            if not _UUID_RE.match(uuid) or uuid in found:
                continue
            found[uuid] = {"uuid": uuid, "name": names.get(uuid),
                           "last_saved": os.path.getmtime(os.path.join(folder, fn))}
    return sorted(found.values(), key=lambda p: p["last_saved"], reverse=True)


def read_player(server_path: str, world_name: str, uuid: str) -> dict:
    uuid = (uuid or "").lower()
    if not _UUID_RE.match(uuid):
        raise ValueError("Invalid player id")
    path = _player_file(server_path, world_name, uuid)
    if not path:
        raise FileNotFoundError(uuid)
    data = parse_player(nbt.load(path))
    data["uuid"] = uuid
    data["name"] = load_names(server_path).get(uuid)
    data["last_saved"] = os.path.getmtime(path)
    return data
