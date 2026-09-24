// "Is this Modrinth project already installed?" resolution.
//
// The on-disk filename heuristic (see installedMatch.js) catches most cases,
// but some projects ship files under a different name than the slug (e.g.
// "simple-voice-chat" installs "voicechat-bukkit-...jar"). The reliable ground
// truth lives on Modrinth: the filenames the project has actually published.
//
// The backend resolves that per project (with a 6h cache) and returns the
// filename lists in one request. We then check the installed jars against them:
//  - exact filename match, or
//  - shared "name-platform" prefix tokens, e.g. a published
//    `voicechat-bukkit-1.20.1-2.3.21.jar` and an installed
//    `voicechat-bukkit-1.0.27.jar` both start with `voicechat-bukkit`.

import { api } from '../api';

function tokens(base) {
    return String(base)
        .toLowerCase()
        .replace(/\.[a-z0-9]+$/, '')
        .split(/[^a-z0-9]+/)
        .filter(Boolean);
}

function matchesPublished(publishedFilenames, installedFilenames) {
    if (!installedFilenames.length) return false;

    const exact = new Set(publishedFilenames);
    // Order matters: exact first, then name-platform prefix.
    const prefixes = [];
    for (const name of installedFilenames) {
        if (exact.has(name)) return true;
        const t = tokens(name);
        if (t.length >= 3) prefixes.push(`${t[0]}-${t[1]}`);
    }
    for (const published of publishedFilenames) {
        const t = tokens(published);
        if (t.length < 3) continue;
        const key = `${t[0]}-${t[1]}`;
        if (prefixes.includes(key)) return true;
    }
    return false;
}

// Resolve which of `slugs` are already installed given the on-disk
// `installed` entries (each with a `filename` field).
export async function resolveInstalledSlugs({ slugs, installed }) {
    const installedFilenames = (installed || [])
        .map((f) => String(f.filename || '').toLowerCase())
        .filter(Boolean);

    const cleanSlugs = (slugs || []).filter(Boolean);
    if (installedFilenames.length === 0 || cleanSlugs.length === 0) return new Set();

    let data = null;
    try {
        data = await api.getProjectFiles(cleanSlugs);
    } catch (e) {
        console.warn('Installed-resolution failed, falling back to heuristic only:', e);
        return new Set();
    }

    const matched = new Set();
    for (const slug of cleanSlugs) {
        const published = data[String(slug).toLowerCase()] || [];
        if (matchesPublished(published, installedFilenames)) matched.add(slug);
    }
    return matched;
}