"""Player skins for the 3D viewer, with the armor the player is wearing.

Skin source, in order:
  1. Premium (version-4) UUIDs: Mojang's session server.
  2. Offline-mode servers (TLauncher etc. use name-based v3 UUIDs): the
     premium account with the same name, if one exists.
  3. The default Steve skin from the locally cached game files.
Skins are cached in <app_data>/skins for a few hours.

Armor is painted onto the skin's outer layer (hat, jacket, sleeves, pants)
using the game's own armor textures, so any skin viewer shows it in 3D
without needing an armor model.
"""

import base64
import io
import json
import os
import re
import time

import requests
from PIL import Image

from utils import mc_assets

SESSION_URL = "https://sessionserver.mojang.com/session/minecraft/profile/{}"
PROFILE_URL = "https://api.mojang.com/users/profiles/minecraft/{}"
CACHE_TTL = 6 * 3600
_UUID_RE = re.compile(r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$")
_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,16}$")

# Armor item id prefix -> (material for 1.21.2+ "equipment", material for older "models/armor")
_MATERIALS = {
    "leather": ("leather", "leather"), "chainmail": ("chainmail", "chainmail"), "iron": ("iron", "iron"),
    "golden": ("gold", "gold"), "diamond": ("diamond", "diamond"), "netherite": ("netherite", "netherite"),
    "copper": ("copper", "copper"), "turtle": ("turtle_scute", "turtle"),
}
_PIECE = {"head": "helmet", "chest": "chestplate", "legs": "leggings", "feet": "boots"}


def valid_uuid(uuid):
    return bool(_UUID_RE.match((uuid or "").lower()))


def _fetch_skin_url(uuid, name):
    """Skin texture URL for a player, or None."""
    plain = uuid.replace("-", "").lower()
    candidates = []
    if len(plain) == 32 and plain[12] == "4":  # Mojang (premium) account
        candidates.append(plain)
    if name and _NAME_RE.match(name):
        try:
            r = requests.get(PROFILE_URL.format(name), timeout=6)
            if r.status_code == 200 and r.json().get("id"):
                candidates.append(r.json()["id"])
        except (requests.RequestException, ValueError):
            pass
    for pid in candidates:
        try:
            r = requests.get(SESSION_URL.format(pid), timeout=6)
            if r.status_code != 200:
                continue
            for prop in r.json().get("properties", []):
                if prop.get("name") == "textures":
                    tex = json.loads(base64.b64decode(prop["value"]))
                    url = (tex.get("textures", {}).get("SKIN") or {}).get("url")
                    if url:
                        return url.replace("http://", "https://")
        except (requests.RequestException, ValueError, KeyError):
            continue
    return None


def _to_64x64(img):
    """Old 64x32 skins: copy right limbs to the left ones so every region exists."""
    if img.height * 2 != img.width:
        return img
    k = img.width // 64
    out = Image.new("RGBA", (img.width, img.width))
    out.alpha_composite(img)
    box = lambda x, y, w, h: (x * k, y * k, (x + w) * k, (y + h) * k)
    out.alpha_composite(img.crop(box(0, 16, 16, 16)), (16 * k, 48 * k))   # right leg -> left leg
    out.alpha_composite(img.crop(box(40, 16, 16, 16)), (32 * k, 48 * k))  # right arm -> left arm
    return out


def base_skin(app_data_dir, uuid, name, roots=None):
    """64x64 RGBA skin for a player (cached), falling back to Steve."""
    uuid = uuid.lower()
    cache_dir = os.path.join(app_data_dir, "skins")
    os.makedirs(cache_dir, exist_ok=True)
    cached = os.path.join(cache_dir, f"{uuid}.png")
    missing = cached + ".none"
    now = time.time()
    if os.path.exists(cached) and now - os.path.getmtime(cached) < CACHE_TTL:
        return Image.open(cached).convert("RGBA")
    if not (os.path.exists(missing) and now - os.path.getmtime(missing) < CACHE_TTL):
        url = _fetch_skin_url(uuid, name)
        if url and url.startswith("https://textures.minecraft.net/"):
            try:
                data = requests.get(url, timeout=8).content
                img = _to_64x64(Image.open(io.BytesIO(data)).convert("RGBA"))
                img.save(cached)
                return img
            except Exception:
                pass
        open(missing, "w").close()
    if os.path.exists(cached):  # stale but better than Steve
        return Image.open(cached).convert("RGBA")
    if roots:
        p = roots.find("minecraft", "textures/entity/player/wide/steve.png")
        if p:
            return _to_64x64(Image.open(p).convert("RGBA"))
    return None


def _armor_texture(roots, item_id, legs):
    ns, path = mc_assets.split_id(item_id)
    if ns != "minecraft":
        return None
    prefix = path.split("_", 1)[0]
    if path == "turtle_helmet":
        prefix = "turtle"
    mats = _MATERIALS.get(prefix)
    if not mats:
        return None
    new_mat, old_mat = mats
    candidates = (
        [f"textures/entity/equipment/humanoid_leggings/{new_mat}.png", f"textures/models/armor/{old_mat}_layer_2.png"]
        if legs else
        [f"textures/entity/equipment/humanoid/{new_mat}.png", f"textures/models/armor/{old_mat}_layer_1.png"]
    )
    for rel in candidates:
        p = roots.find("minecraft", rel)
        if p:
            img = Image.open(p).convert("RGBA")
            if prefix == "leather":
                img = mc_assets._tint_img(img, mc_assets.LEATHER_TINT)
            return img
    return None


def apply_armor(skin, armor, roots):
    """Paint worn armor ({head, chest, legs, feet: item}) onto the outer layer.

    Armor textures use the 64x32 humanoid layout; their regions map onto the
    skin's overlay regions (hat, jacket, sleeves, pants).
    """
    if not skin or not armor or not roots:
        return skin
    out = skin.copy()
    k = out.width // 64

    def paste(tex, src, dst):
        tk = tex.width / 64.0
        x, y, w, h = src
        part = tex.crop((int(x * tk), int(y * tk), int((x + w) * tk), int((y + h) * tk)))
        part = part.resize((w * k, h * k), Image.NEAREST)
        out.alpha_composite(part, (dst[0] * k, dst[1] * k))

    # Leggings first, so the chestplate and boots sit over them.
    order = (("legs", True), ("head", False), ("chest", False), ("feet", False))
    for slot, legs in order:
        item = armor.get(slot)
        if not item:
            continue
        tex = _armor_texture(roots, item.get("id", ""), legs)
        if not tex:
            continue
        if slot == "head":
            paste(tex, (0, 0, 32, 16), (32, 0))
        elif slot == "chest":
            paste(tex, (16, 16, 24, 16), (16, 32))
            paste(tex, (40, 16, 16, 16), (40, 32))
            paste(tex, (40, 16, 16, 16), (48, 48))
        elif slot == "legs":
            paste(tex, (16, 16, 24, 16), (16, 32))
            paste(tex, (0, 16, 16, 16), (0, 32))
            paste(tex, (0, 16, 16, 16), (0, 48))
        elif slot == "feet":
            paste(tex, (0, 16, 16, 16), (0, 32))
            paste(tex, (0, 16, 16, 16), (0, 48))
    return out


def skin_png(app_data_dir, uuid, name, armor=None, roots=None):
    """PNG bytes of the player's skin with armor applied, or None."""
    skin = base_skin(app_data_dir, uuid, name, roots)
    if skin is None:
        return None
    skin = apply_armor(skin, armor or {}, roots)
    buf = io.BytesIO()
    skin.save(buf, "PNG")
    return buf.getvalue()
