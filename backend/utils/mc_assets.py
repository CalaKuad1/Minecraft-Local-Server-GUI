"""Item icons and names for the inventory inspector, built on the user's PC.

Cubi does not ship any Mojang artwork. The first time someone opens the
inspector (and accepts the Minecraft EULA), this downloads the official
client jar for a version from Mojang's servers (the same source the launcher
uses), keeps only the textures/models/lang files it needs, deletes the jar and
renders icons locally: flat items as-is, blocks as a small 3D cube like the
in-game inventory. Same idea as BlueMap/Dynmap.

Vanilla files are cached per Minecraft version and shared by every server;
when the exact version is missing, any other cached version is used (items
barely change). Modded items come from the mod jars already in the server's
mods/ folder, extracted on demand per namespace.
"""

import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import zipfile

import requests
from PIL import Image, ImageDraw, ImageEnhance

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
RESOURCES_URL = "https://resources.download.minecraft.net"
ICON_SIZE = 128
_NS_RE = re.compile(r"^[a-z0-9_.-]{1,64}$")
_PATH_RE = re.compile(r"^[a-z0-9_./-]{1,128}$")
# Kept from jars (relative to assets/<namespace>/).
_KEEP_SUBDIRS = ("textures/item/", "textures/block/", "models/item/", "models/block/", "items/", "lang/")
_KEEP_VANILLA_EXTRA = (
    "textures/colormap/", "textures/entity/chest/", "textures/entity/shield_base_nopattern.png",
    "textures/entity/player/wide/steve.png", "textures/entity/zombie/zombie.png",
    "textures/entity/skeleton/skeleton.png", "textures/entity/skeleton/wither_skeleton.png",
    "textures/entity/creeper/creeper.png",
)
# App language -> Mojang locale file.
LOCALES = {"en": "en_us", "es": "es_es", "fr": "fr_fr", "ru": "ru_ru"}

GRASS_TINT = (124, 189, 107)
FOLIAGE_TINT = (89, 174, 48)
LEATHER_TINT = (160, 101, 64)
_TINTS = {
    "grass_block_top": GRASS_TINT, "grass_block_side_overlay": GRASS_TINT, "short_grass": GRASS_TINT,
    "grass": GRASS_TINT, "tall_grass_top": GRASS_TINT, "tall_grass_bottom": GRASS_TINT, "fern": GRASS_TINT,
    "large_fern_top": GRASS_TINT, "large_fern_bottom": GRASS_TINT, "sugar_cane": GRASS_TINT,
    "vine": FOLIAGE_TINT, "lily_pad": (32, 128, 48),
    "spruce_leaves": (97, 153, 97), "birch_leaves": (128, 167, 85),
    "leather_helmet": LEATHER_TINT, "leather_chestplate": LEATHER_TINT, "leather_leggings": LEATHER_TINT,
    "leather_boots": LEATHER_TINT, "leather_horse_armor": LEATHER_TINT, "wolf_armor_dyed": LEATHER_TINT,
}
# Items drawn by the game's entity renderer instead of a model: (texture, kind)
_SPECIAL = {
    "chest": ("entity/chest/normal", "chest"), "trapped_chest": ("entity/chest/trapped", "chest"),
    "ender_chest": ("entity/chest/ender", "chest"), "shield": ("entity/shield_base_nopattern", "shield"),
    "player_head": ("entity/player/wide/steve", "head"), "zombie_head": ("entity/zombie/zombie", "head"),
    "skeleton_skull": ("entity/skeleton/skeleton", "head"),
    "wither_skeleton_skull": ("entity/skeleton/wither_skeleton", "head"),
    "creeper_head": ("entity/creeper/creeper", "head"),
}


class AssetError(Exception):
    pass


def split_id(item_id):
    ns, _, path = (item_id or "").partition(":")
    return (ns, path) if path else ("minecraft", ns)


def _cache_root(app_data_dir):
    return os.path.join(app_data_dir, "mc_assets")


def _version_dir(app_data_dir, version):
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", version or "")
    return os.path.join(_cache_root(app_data_dir), safe)


def cached_versions(app_data_dir):
    root = _cache_root(app_data_dir)
    try:
        return sorted(
            (d for d in os.listdir(root) if os.path.exists(os.path.join(root, d, ".complete"))),
            key=lambda d: os.path.getmtime(os.path.join(root, d, ".complete")),
            reverse=True,
        )
    except OSError:
        return []


def pick_version(app_data_dir, wanted):
    """Exact cached version if present, otherwise the newest cached one."""
    versions = cached_versions(app_data_dir)
    if not versions:
        return None
    safe = os.path.basename(_version_dir(app_data_dir, wanted or ""))
    return safe if safe in versions else versions[0]


# --------------------------------------------------------------- download

class Downloader:
    """One background download at a time, with progress for the UI."""

    def __init__(self):
        self.lock = threading.Lock()
        self.state = {"running": False, "version": None, "progress": 0, "error": None}

    def status(self):
        with self.lock:
            return dict(self.state)

    def start(self, app_data_dir, version, locale="en_us"):
        with self.lock:
            if self.state["running"]:
                return False
            self.state = {"running": True, "version": version, "progress": 0, "error": None}
        threading.Thread(target=self._run, args=(app_data_dir, version, locale), daemon=True).start()
        return True

    def _set(self, **kw):
        with self.lock:
            self.state.update(kw)

    def _run(self, app_data_dir, version, locale):
        try:
            download_version(app_data_dir, version, locale, progress=lambda p: self._set(progress=p))
            self._set(running=False, progress=100)
        except Exception as e:  # surfaced to the UI as text
            self._set(running=False, error=str(e))


def _version_json(version):
    manifest = requests.get(MANIFEST_URL, timeout=15).json()
    entry = next((v for v in manifest.get("versions", []) if v.get("id") == version), None)
    if not entry:
        # Unknown id (custom/modded label): fall back to the latest release.
        latest = manifest.get("latest", {}).get("release")
        entry = next((v for v in manifest.get("versions", []) if v.get("id") == latest), None)
    if not entry:
        raise AssetError(f"Version {version} not found in Mojang's manifest")
    return requests.get(entry["url"], timeout=15).json()


def _extract(jar, dest_for_ns, keep_extra=()):
    """Copy wanted assets/<ns>/... entries out of a jar. dest_for_ns(ns) -> dir or None."""
    for info in jar.infolist():
        name = info.filename
        if info.is_dir() or ".." in name or not name.startswith("assets/"):
            continue
        parts = name.split("/", 2)
        if len(parts) < 3:
            continue
        ns, rel = parts[1], parts[2]
        if not (rel.startswith(_KEEP_SUBDIRS) or (ns == "minecraft" and rel.startswith(keep_extra))):
            continue
        if not rel.endswith((".png", ".json", ".mcmeta")):
            continue
        if rel.startswith("lang/") and not rel.endswith(("en_us.json", "es_es.json", "fr_fr.json", "ru_ru.json")):
            continue
        dest = dest_for_ns(ns)
        if not dest:
            continue
        out = os.path.join(dest, *rel.split("/"))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with jar.open(info) as src, open(out, "wb") as f:
            shutil.copyfileobj(src, f)


def download_version(app_data_dir, version, locale="en_us", progress=lambda p: None):
    meta = _version_json(version)
    client = meta["downloads"]["client"]
    dest = _version_dir(app_data_dir, version)
    os.makedirs(dest, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jar")
    try:
        sha1 = hashlib.sha1()
        done, total = 0, int(client.get("size") or 1)
        with requests.get(client["url"], stream=True, timeout=30) as r:
            r.raise_for_status()
            for chunk in r.iter_content(1 << 16):
                tmp.write(chunk)
                sha1.update(chunk)
                done += len(chunk)
                progress(min(85, int(done * 85 / total)))
        tmp.close()
        if client.get("sha1") and sha1.hexdigest() != client["sha1"]:
            raise AssetError("Downloaded client jar failed its checksum")
        with zipfile.ZipFile(tmp.name) as jar:
            _extract(jar, lambda ns: dest if ns == "minecraft" else None, _KEEP_VANILLA_EXTRA)
        progress(90)
        if locale and locale != "en_us":
            fetch_locale(dest, meta, locale)
        with open(os.path.join(dest, ".complete"), "w") as f:
            f.write(version)
        progress(100)
    finally:
        try:
            tmp.close()
            os.unlink(tmp.name)
        except OSError:
            pass


def fetch_locale(dest, meta, locale):
    """Vanilla translations live outside the jar, in the asset index."""
    try:
        index = requests.get(meta["assetIndex"]["url"], timeout=15).json()
        obj = index["objects"].get(f"minecraft/lang/{locale}.json")
        if not obj:
            return
        h = obj["hash"]
        data = requests.get(f"{RESOURCES_URL}/{h[:2]}/{h}", timeout=30).content
        if hashlib.sha1(data).hexdigest() == h:
            os.makedirs(os.path.join(dest, "lang"), exist_ok=True)
            with open(os.path.join(dest, "lang", f"{locale}.json"), "wb") as f:
                f.write(data)
    except Exception:
        pass  # names fall back to English


def ensure_locale(app_data_dir, version, locale):
    dest = _version_dir(app_data_dir, version)
    if locale == "en_us" or os.path.exists(os.path.join(dest, "lang", f"{locale}.json")):
        return
    try:
        fetch_locale(dest, _version_json(version), locale)
    except Exception:
        pass


# ------------------------------------------------------------- mod assets

_mod_index_lock = threading.Lock()
_mod_index = {}  # mods_dir -> (signature, {namespace: [jar paths]})
_extract_lock = threading.Lock()


def _mods_signature(mods_dir):
    try:
        jars = sorted(f for f in os.listdir(mods_dir) if f.endswith(".jar"))
    except OSError:
        return None, []
    sig = hashlib.sha1()
    for f in jars:
        st = os.stat(os.path.join(mods_dir, f))
        sig.update(f"{f}:{st.st_size}:{int(st.st_mtime)}".encode())
    return sig.hexdigest(), jars


def mod_namespaces(server_path):
    """{namespace: [jar paths]} for the mods in a server (cached). Add-ons often
    ship files under their parent mod's namespace, so one namespace can span
    several jars."""
    mods_dir = os.path.join(server_path or "", "mods")
    sig, jars = _mods_signature(mods_dir)
    if not sig:
        return {}
    with _mod_index_lock:
        cached = _mod_index.get(mods_dir)
        if cached and cached[0] == sig:
            return cached[1]
    found = {}
    for f in jars:
        path = os.path.join(mods_dir, f)
        try:
            with zipfile.ZipFile(path) as jar:
                for name in jar.namelist():
                    if name.startswith("assets/"):
                        parts = name.split("/")
                        if len(parts) > 2 and parts[1] != "minecraft" and _NS_RE.match(parts[1]):
                            jars_for = found.setdefault(parts[1], [])
                            if path not in jars_for:
                                jars_for.append(path)
        except (OSError, zipfile.BadZipFile):
            continue
    with _mod_index_lock:
        _mod_index[mods_dir] = (sig, found)
    return found


def _mod_root(app_data_dir, jar_path, ns):
    st = os.stat(jar_path)
    key = hashlib.sha1(f"{os.path.basename(jar_path)}:{st.st_size}:{int(st.st_mtime)}".encode()).hexdigest()[:16]
    root = os.path.join(app_data_dir, "mod_assets", key)
    marker = os.path.join(root, ".complete")
    if not os.path.exists(marker):
        # Icon requests arrive in parallel; extract each jar only once.
        with _extract_lock:
            if not os.path.exists(marker):
                os.makedirs(root, exist_ok=True)
                with zipfile.ZipFile(jar_path) as jar:
                    _extract(jar, lambda n: os.path.join(root, n) if _NS_RE.match(n) and n != "minecraft" else None)
                with open(marker, "w") as f:
                    f.write(os.path.basename(jar_path))
    return os.path.join(root, ns)


class Roots:
    """Where each namespace's assets live: vanilla cache + mod jars (lazy).

    A namespace maps to a list of directories, searched in order."""

    def __init__(self, app_data_dir, version, server_path=None):
        self.app_data_dir = app_data_dir
        self.vanilla = _version_dir(app_data_dir, version)
        self.server_path = server_path
        self._cache = {"minecraft": [self.vanilla]}

    def dirs(self, ns):
        if ns in self._cache:
            return self._cache[ns]
        out = []
        jars = mod_namespaces(self.server_path).get(ns, []) if self.server_path else []
        for jar in jars:
            try:
                d = _mod_root(self.app_data_dir, jar, ns)
            except (OSError, zipfile.BadZipFile):
                continue
            if os.path.isdir(d):
                out.append(d)
        self._cache[ns] = out
        return out

    def find(self, ns, rel):
        for d in self.dirs(ns):
            p = os.path.join(d, *rel.split("/"))
            if os.path.exists(p):
                return p
        return None

    def icon_dir(self, ns):
        if ns == "minecraft":
            return os.path.join(self.vanilla, "icons")
        jars = mod_namespaces(self.server_path).get(ns) if self.server_path else None
        if not jars:
            return None
        # Keyed by the mods folder's contents, so updating a mod re-renders its icons.
        sig, _ = _mods_signature(os.path.join(self.server_path, "mods"))
        return os.path.join(self.app_data_dir, "mod_assets", "icons", (sig or "none")[:12], ns)


# ------------------------------------------------------------------ names

def item_names(roots, namespaces=(), locale="en_us"):
    """Merged translation keys for vanilla + the given mod namespaces."""
    names = {}
    for ns in ["minecraft", *[n for n in namespaces if n != "minecraft"]]:
        for base in roots.dirs(ns):
            for loc in ("en_us", locale):
                try:
                    with open(os.path.join(base, "lang", f"{loc}.json"), "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        names.update(data)
                except (OSError, ValueError):
                    pass
    return names


def display_name(names, item_id):
    ns, path = split_id(item_id)
    key_path = path.replace("/", ".")
    return (names.get(f"item.{ns}.{key_path}") or names.get(f"block.{ns}.{key_path}")
            or path.split("/")[-1].replace("_", " ").capitalize())


def enchantment_name(names, ench_id):
    ns, path = split_id(ench_id)
    return names.get(f"enchantment.{ns}.{path}") or path.replace("_", " ").capitalize()


# ---------------------------------------------------------------- models

def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _model_ref_from_item_def(node):
    """Pick a model from a 1.21.4+ item definition (first plain model found)."""
    if isinstance(node, dict):
        if node.get("type") in ("minecraft:model", "model") and isinstance(node.get("model"), str):
            return node["model"]
        if node.get("type") in ("minecraft:special", "special") and isinstance(node.get("base"), str):
            return node["base"]
        for key in ("fallback", "model", "on_false", "on_true", "cases", "entries", "models"):
            if key in node:
                found = _model_ref_from_item_def(node[key])
                if found:
                    return found
        for v in node.values():
            found = _model_ref_from_item_def(v)
            if found:
                return found
    elif isinstance(node, list):
        for v in node:
            found = _model_ref_from_item_def(v)
            if found:
                return found
    return None


def _qualify(ref, default_ns="minecraft"):
    """'create:item/x' -> ('create', 'item/x'); bare refs are minecraft's."""
    if ":" in ref:
        ns, path = ref.split(":", 1)
        return ns, path
    return default_ns, ref


def resolve_model(roots, item_id):
    """Follow the parent chain. Returns (chain of 'ns:path', merged textures)."""
    ns, path = split_id(item_id)
    ref = None
    def_file = roots.find(ns, f"items/{path}.json")
    item_def = _load_json(def_file) if def_file else None
    if item_def:
        ref = _model_ref_from_item_def(item_def.get("model"))
    cur = _qualify(ref) if ref else (ns, f"item/{path}")
    # Some mods register block items without an item model file.
    if not ref and not roots.find(ns, f"models/item/{path}.json") and roots.find(ns, f"models/block/{path}.json"):
        cur = (ns, f"block/{path}")
    chain, textures, seen = [], {}, set()
    while cur and cur not in seen and len(chain) < 16:
        seen.add(cur)
        chain.append(f"{cur[0]}:{cur[1]}")
        mfile = roots.find(cur[0], f"models/{cur[1]}.json")
        model = _load_json(mfile) if mfile else None
        if not model:
            break
        for k, v in (model.get("textures") or {}).items():
            if isinstance(v, str):
                textures.setdefault(k, v)
        parent = model.get("parent")
        cur = _qualify(parent) if parent else None
    return chain, textures


def _tex_file(roots, ref):
    ns, path = _qualify(ref)
    return roots.find(ns, f"textures/{path}.png")


def _tex_path(roots, textures, key, depth=0):
    v = textures.get(key)
    if not v or depth > 8:
        return None
    if v.startswith("#"):
        return _tex_path(roots, textures, v[1:], depth + 1)
    return _tex_file(roots, v)


def _tint_img(img, tint):
    r, g, b, a = img.split()
    lum = Image.merge("RGB", (r, g, b)).convert("L")
    return Image.merge("RGBA", tuple(lum.point(lambda v, c=c: v * c // 255) for c in tint) + (a,))


def _open_tex(path):
    img = Image.open(path).convert("RGBA")
    if img.height > img.width and img.height % img.width == 0:  # animated strip: first frame
        img = img.crop((0, 0, img.width, img.width))
    name = os.path.splitext(os.path.basename(path))[0]
    tint = _TINTS.get(name)
    if not tint and name.endswith("_leaves") and not name.startswith(
            ("cherry", "azalea", "flowering", "pale_oak", "mangrove")) and "minecraft" in path.replace("\\", "/"):
        tint = FOLIAGE_TINT
    return _tint_img(img, tint) if tint else img


def _flat(paths):
    out = None
    for p in paths:
        layer = _open_tex(p)
        if out is None:
            out = Image.new("RGBA", layer.size)
        out.alpha_composite(layer.resize(out.size, Image.NEAREST))
    return _fit(out) if out else None


def _fit(img):
    """Scale to the icon size, keeping aspect ratio, pixel-crisp."""
    scale = ICON_SIZE / max(img.size)
    img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.NEAREST)
    out = Image.new("RGBA", (ICON_SIZE, ICON_SIZE))
    out.alpha_composite(img, ((ICON_SIZE - img.width) // 2, (ICON_SIZE - img.height) // 2))
    return out


def _face(tex, size, origin, u, v, out):
    """Paint `tex` onto the parallelogram origin + s*u + t*v (s,t in 0..1)."""
    tex = tex.resize((64, 64), Image.NEAREST)
    det = u[0] * v[1] - u[1] * v[0]
    if det == 0:
        return
    ia, ib = v[1] / det, -v[0] / det
    ic, id_ = -u[1] / det, u[0] / det
    coeffs = (
        64 * ia, 64 * ib, -64 * (ia * origin[0] + ib * origin[1]),
        64 * ic, 64 * id_, -64 * (ic * origin[0] + id_ * origin[1]),
    )
    layer = tex.transform((size, size), Image.AFFINE, coeffs, resample=Image.NEAREST)
    mask = Image.new("L", (size, size), 0)
    pts = [origin, (origin[0] + u[0], origin[1] + u[1]),
           (origin[0] + u[0] + v[0], origin[1] + u[1] + v[1]), (origin[0] + v[0], origin[1] + v[1])]
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", (size, size), 0), mask))
    out.alpha_composite(layer)


def _shade(img, factor):
    rgb = ImageEnhance.Brightness(img.convert("RGB")).enhance(factor)
    rgb.putalpha(img.getchannel("A"))
    return rgb


def _cube(top, left, right, height=1.0):
    s = ICON_SIZE
    m = s / 64.0
    h = 30 * m * height
    drop = 30 * m * (1 - height)
    out = Image.new("RGBA", (s, s))
    _face(_shade(left, 0.82), s, (2 * m, 17 * m + drop), (30 * m, 15 * m), (0, h), out)
    _face(_shade(right, 0.62), s, (32 * m, 32 * m + drop), (30 * m, -15 * m), (0, h), out)
    _face(top, s, (2 * m, 17 * m + drop), (30 * m, -15 * m), (30 * m, 15 * m), out)
    return out


def _stack(*parts):
    """Stack image crops vertically (all same width)."""
    w = max(p.width for p in parts)
    out = Image.new("RGBA", (w, sum(p.height for p in parts)))
    y = 0
    for p in parts:
        out.alpha_composite(p, (0, y))
        y += p.height
    return out


def _render_special(roots, item_path):
    tex_ref, kind = _SPECIAL[item_path]
    p = _tex_file(roots, tex_ref)
    if not p:
        return None
    img = Image.open(p).convert("RGBA")
    k = img.width / 64.0  # HD packs scale the atlas
    c = lambda x0, y0, x1, y1: img.crop(tuple(int(v * k) for v in (x0, y0, x1, y1)))
    if kind == "chest":
        # Box UV layout: lid (14x5x14) at v=0, base (14x10x14) at v=19.
        top = c(14, 0, 28, 14)
        front = _stack(c(14, 14, 28, 19), c(14, 33, 28, 43))
        side = _stack(c(0, 14, 14, 19), c(0, 33, 14, 43))
        icon = _cube(top, side, front, 0.9)
        latch = c(1, 1, 3, 5)  # small lock
        if latch.getbbox():
            m = ICON_SIZE / 64.0
            latch = latch.resize((int(4 * m), int(7 * m)), Image.NEAREST)
            icon.alpha_composite(latch, (int(45 * m), int(33 * m)))
        return icon
    if kind == "shield":
        return _fit(c(1, 1, 13, 23))
    if kind == "head":
        top, front, side = c(8, 0, 16, 8), c(8, 8, 16, 16), c(0, 8, 8, 16)
        for (x0, y0, x1, y1), base in (((40, 8, 48, 16), front), ((40, 0, 48, 8), top), ((32, 8, 40, 16), side)):
            hat = c(x0, y0, x1, y1)
            if hat.getbbox():
                base.alpha_composite(hat.resize(base.size, Image.NEAREST))
        return _cube(top, side, front, 1.0)
    return None


def render_icon(roots, item_id):
    ns, path = split_id(item_id)
    if ns == "minecraft" and path in _SPECIAL:
        icon = _render_special(roots, path)
        if icon:
            return icon
    chain, textures = resolve_model(roots, item_id)
    names = {c.split(":", 1)[1] for c in chain}
    is_flat = any(n in ("item/generated", "builtin/generated") or n.startswith("item/handheld") for n in names)
    has_block = any(n.startswith("block/") for n in names)
    if is_flat or not has_block:
        layers = []
        for i in range(8):
            p = _tex_path(roots, textures, f"layer{i}")
            if not p:
                break
            layers.append(p)
        if not layers:
            for guess in (f"{ns}:item/{path}", f"{ns}:block/{path}"):
                p = _tex_file(roots, guess)
                if p:
                    layers = [p]
                    break
        if not layers:
            for key in ("particle", *textures.keys()):
                p = _tex_path(roots, textures, key)
                if p:
                    layers = [p]
                    break
        return _flat(layers) if layers else None

    def pick(*keys):
        for k in keys:
            p = _tex_path(roots, textures, k)
            if p:
                return _open_tex(p)
        return None

    top = pick("up", "top", "end", "all", "texture", "side", "particle")
    side = pick("north", "south", "side", "all", "texture", "particle")
    front = pick("front", "south", "east", "side", "all", "texture", "particle") or side
    if not (top and side):
        p = _tex_path(roots, textures, "particle") or _tex_file(roots, f"{ns}:block/{path}")
        return _flat([p]) if p else None
    overlay = _tex_path(roots, textures, "overlay")
    if overlay:  # grass block side: biome-tinted overlay on dirt
        side = side.copy()
        side.alpha_composite(_open_tex(overlay).resize(side.size, Image.NEAREST))
        front = side
    height = 0.5 if any("slab" in n for n in names) else 1.0
    return _cube(top, side, front, height)


def icon_path(roots, item_id):
    """Rendered icon file for an item (rendered and cached on first request)."""
    ns, path = split_id(item_id)
    if not _NS_RE.match(ns) or not _PATH_RE.match(path) or ".." in path:
        raise AssetError("Invalid item id")
    out_dir = roots.icon_dir(ns)
    if not out_dir:
        return None
    out = os.path.join(out_dir, *path.split("/")) + ".png"
    miss = out + ".missing"
    if os.path.exists(out):
        return out
    if os.path.exists(miss):
        return None
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        img = render_icon(roots, f"{ns}:{path}")
    except Exception:
        img = None
    if img is None:
        open(miss, "w").close()
        return None
    img.save(out)
    return out
