import gzip
import json
import os
import struct
import sys
import tempfile
import zipfile

import pytest
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils import mc_assets, nbt, player_data  # noqa: E402

UUID = "1bb219bb-0000-4000-8000-000000000001"


# ---------------------------------------------------------- tiny NBT writer

def _s(text):
    b = text.encode("utf-8")
    return struct.pack(">H", len(b)) + b


def _tag(value):
    """(tag id, payload bytes) for a Python value."""
    if isinstance(value, bool) or (isinstance(value, tuple) and value[0] == "b"):
        v = value[1] if isinstance(value, tuple) else int(value)
        return 1, struct.pack(">b", v)
    if isinstance(value, tuple) and value[0] == "f":
        return 5, struct.pack(">f", value[1])
    if isinstance(value, tuple) and value[0] == "d":
        return 6, struct.pack(">d", value[1])
    if isinstance(value, int):
        return 3, struct.pack(">i", value)
    if isinstance(value, str):
        return 8, _s(value)
    if isinstance(value, dict):
        out = b""
        for k, v in value.items():
            tid, payload = _tag(v)
            out += struct.pack(">b", tid) + _s(k) + payload
        return 10, out + b"\x00"
    if isinstance(value, list):
        if not value:
            return 9, struct.pack(">bi", 0, 0)
        tags = [_tag(v) for v in value]
        return 9, struct.pack(">bi", tags[0][0], len(tags)) + b"".join(p for _, p in tags)
    raise TypeError(value)


def nbt_file(root: dict) -> bytes:
    _, payload = _tag(root)
    return gzip.compress(b"\x0a" + _s("") + payload)


# ------------------------------------------------------------------- NBT

def test_nbt_roundtrip_types():
    data = nbt.loads(nbt_file({"a": 5, "b": ("b", -3), "f": ("f", 1.5), "s": "hé", "l": [1, 2], "c": {"x": "y"}}))
    assert data == {"a": 5, "b": -3, "f": 1.5, "s": "hé", "l": [1, 2], "c": {"x": "y"}}


def test_nbt_rejects_garbage():
    with pytest.raises(nbt.NBTError):
        nbt.loads(b"\x08\x00\x00")


# ------------------------------------------------------------ player data

MODERN = {
    "Inventory": [
        {"Slot": ("b", 0), "id": "minecraft:diamond_sword", "count": 1, "components": {
            "minecraft:damage": 61,
            "minecraft:enchantments": {"levels": {"minecraft:sharpness": 5}},
            "minecraft:custom_name": '{"text":"Excalibur"}',
        }},
        {"Slot": ("b", 8), "id": "create:wrench", "count": 1},
        {"Slot": ("b", 9), "id": "minecraft:air", "count": 1},
    ],
    "equipment": {"head": {"id": "minecraft:iron_helmet", "count": 1}, "offhand": {"id": "minecraft:shield", "count": 1}},
    "EnderItems": [{"Slot": ("b", 3), "id": "minecraft:enchanted_book", "count": 1, "components": {
        "minecraft:stored_enchantments": {"minecraft:mending": 1}}}],
    "Health": ("f", 17.5), "foodLevel": 18, "XpLevel": 30, "playerGameType": 1,
    "Dimension": "minecraft:the_nether", "Pos": [("d", 1.26), ("d", 64.0), ("d", -3.5)],
}

LEGACY = {
    "Inventory": [
        {"Slot": ("b", 1), "id": "minecraft:bow", "Count": ("b", 1), "tag": {
            "Damage": 84, "Enchantments": [{"id": "minecraft:power", "lvl": 3}],
            "display": {"Name": '{"text":"Old bow"}'}}},
        {"Slot": ("b", 103), "id": "minecraft:diamond_helmet", "Count": ("b", 1)},
        {"Slot": ("b", 100), "id": "minecraft:diamond_boots", "Count": ("b", 1)},
        {"Slot": ("b", -106), "id": "minecraft:torch", "Count": ("b", 32)},
    ],
}


def test_parse_modern_player():
    d = player_data.parse_player(nbt.loads(nbt_file(MODERN)))
    sword = d["inventory"][0]
    assert sword["id"] == "minecraft:diamond_sword" and sword["slot"] == 0
    assert sword["custom_name"] == "Excalibur"
    assert sword["enchantments"] == [{"id": "minecraft:sharpness", "level": 5}]
    assert sword["durability"] == {"remaining": 1500, "max": 1561}
    assert d["inventory"][1]["id"] == "create:wrench"  # modded id keeps its namespace
    assert len(d["inventory"]) == 2  # air dropped
    assert d["armor"]["head"]["id"] == "minecraft:iron_helmet"
    assert d["offhand"]["id"] == "minecraft:shield"
    assert d["ender_chest"][0]["stored_enchantments"] == [{"id": "minecraft:mending", "level": 1}]
    st = d["stats"]
    assert (st["health"], st["food"], st["xp_level"], st["gamemode"], st["dimension"]) == (17.5, 18, 30, "creative", "the_nether")
    assert st["position"] == [1.3, 64.0, -3.5]


def test_parse_legacy_player():
    d = player_data.parse_player(nbt.loads(nbt_file(LEGACY)))
    bow = d["inventory"][0]
    assert bow["custom_name"] == "Old bow"
    assert bow["enchantments"] == [{"id": "minecraft:power", "level": 3}]
    assert bow["durability"] == {"remaining": 300, "max": 384}
    assert d["armor"]["head"]["id"] == "minecraft:diamond_helmet"
    assert d["armor"]["feet"]["id"] == "minecraft:diamond_boots"
    assert d["offhand"]["count"] == 32


def test_list_and_read_players_from_world():
    with tempfile.TemporaryDirectory() as srv:
        pd_dir = os.path.join(srv, "world", "playerdata")
        os.makedirs(pd_dir)
        with open(os.path.join(pd_dir, f"{UUID}.dat"), "wb") as f:
            f.write(nbt_file(MODERN))
        open(os.path.join(pd_dir, "not-a-player.dat"), "w").close()
        with open(os.path.join(srv, "usercache.json"), "w") as f:
            json.dump([{"name": "Steve", "uuid": UUID}], f)
        players = player_data.list_players(srv, "world")
        assert [(p["uuid"], p["name"]) for p in players] == [(UUID, "Steve")]
        d = player_data.read_player(srv, "world", UUID)
        assert d["name"] == "Steve" and d["inventory"]
        with pytest.raises(ValueError):
            player_data.read_player(srv, "world", "../../etc/passwd")


# ------------------------------------------------------------ item icons

def _png(path, color=(200, 50, 50, 255), size=16):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("RGBA", (size, size), color).save(path)


def _json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


@pytest.fixture
def vanilla(tmp_path):
    app = str(tmp_path)
    base = mc_assets._version_dir(app, "1.21.1")
    _png(os.path.join(base, "textures", "item", "apple.png"))
    _json(os.path.join(base, "models", "item", "apple.json"), {"parent": "minecraft:item/generated", "textures": {"layer0": "minecraft:item/apple"}})
    _json(os.path.join(base, "models", "item", "generated.json"), {})
    _png(os.path.join(base, "textures", "block", "stone.png"), (120, 120, 120, 255))
    _json(os.path.join(base, "models", "block", "cube_all.json"), {"parent": "block/cube", "textures": {"particle": "#all", "up": "#all", "north": "#all"}})
    _json(os.path.join(base, "models", "block", "stone.json"), {"parent": "minecraft:block/cube_all", "textures": {"all": "minecraft:block/stone"}})
    _json(os.path.join(base, "models", "item", "stone.json"), {"parent": "minecraft:block/stone"})
    _json(os.path.join(base, "items", "stone.json"), {"model": {"type": "minecraft:model", "model": "minecraft:block/stone"}})
    open(os.path.join(base, ".complete"), "w").close()
    return app


def test_flat_and_block_icons(vanilla):
    roots = mc_assets.Roots(vanilla, "1.21.1")
    apple = Image.open(mc_assets.icon_path(roots, "minecraft:apple"))
    assert apple.size == (mc_assets.ICON_SIZE, mc_assets.ICON_SIZE)
    assert apple.getpixel((64, 64))[:3] == (200, 50, 50)
    stone = Image.open(mc_assets.icon_path(roots, "stone"))  # bare id = minecraft
    # 3D cube: corners transparent, top face lit, sides darker
    assert stone.getpixel((2, 2))[3] == 0
    top, right = stone.getpixel((64, 34)), stone.getpixel((100, 90))
    assert top[3] == 255 and right[3] == 255 and right[0] < top[0]


def test_missing_and_invalid_icons(vanilla):
    roots = mc_assets.Roots(vanilla, "1.21.1")
    assert mc_assets.icon_path(roots, "minecraft:does_not_exist") is None
    with pytest.raises(mc_assets.AssetError):
        mc_assets.icon_path(roots, "minecraft:../../secret")


def test_pick_version_falls_back_to_cached(vanilla):
    assert mc_assets.pick_version(vanilla, "1.21.1") == "1.21.1"
    assert mc_assets.pick_version(vanilla, "1.20.4") == "1.21.1"


def test_mod_icons_and_names_from_jars(vanilla, tmp_path):
    srv = tmp_path / "srv"
    (srv / "mods").mkdir(parents=True)
    tex = tmp_path / "wrench.png"
    Image.new("RGBA", (16, 16), (10, 200, 10, 255)).save(tex)
    with zipfile.ZipFile(srv / "mods" / "create.jar", "w") as z:
        z.write(tex, "assets/create/textures/item/wrench.png")
        z.writestr("assets/create/models/item/wrench.json", json.dumps({"parent": "item/generated", "textures": {"layer0": "create:item/wrench"}}))
        z.writestr("assets/create/lang/en_us.json", json.dumps({"item.create.wrench": "Wrench"}))
    # an add-on shipping translations under the parent mod's namespace
    with zipfile.ZipFile(srv / "mods" / "create_addon.jar", "w") as z:
        z.writestr("assets/create/lang/es_es.json", json.dumps({"item.create.wrench": "Llave inglesa"}))
    roots = mc_assets.Roots(vanilla, "1.21.1", str(srv))
    assert set(mc_assets.mod_namespaces(str(srv))) == {"create"}
    icon = Image.open(mc_assets.icon_path(roots, "create:wrench"))
    assert icon.getpixel((64, 64))[:3] == (10, 200, 10)
    names = mc_assets.item_names(roots, {"create"}, "es_es")
    assert mc_assets.display_name(names, "create:wrench") == "Llave inglesa"
    assert mc_assets.display_name(names, "create:unknown_thing") == "Unknown thing"


def test_players_folder_of_minecraft_26():
    # 26.x stores player files in <world>/players/data instead of playerdata
    with tempfile.TemporaryDirectory() as srv:
        d = os.path.join(srv, "world", "players", "data")
        os.makedirs(d)
        with open(os.path.join(d, f"{UUID}.dat"), "wb") as f:
            f.write(nbt_file(MODERN))
        assert [p["uuid"] for p in player_data.list_players(srv, "world")] == [UUID]
        assert player_data.read_player(srv, "world", UUID)["inventory"]
        with pytest.raises(FileNotFoundError):
            player_data.read_player(srv, "world", "00000000-0000-4000-8000-000000000000")
