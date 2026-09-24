// Heuristic match: is a Modrinth project (by `slug`) already on disk among the
// installed files (e.g. the jar files listed by /mods/installed or /plugins)?
//
// Modrinth auto-generates artifact filenames like
// `sodium-fabric-mc1.20.1-0.5.8.jar` or `fabric-api-0.97.0+1.20.4.jar`, so the
// project slug is almost always a token in the filename. Matching on full
// tokens avoids short-slug false positives ("api" matching "pixelapicore");
// for hyphenated slugs (fabric-api) we fall back to a substring check long
// enough to stay meaningful.
export function isSlugInstalled(slug, installedList = []) {
    const slugLower = String(slug || '').toLowerCase();
    if (!slugLower) return false;

    return installedList.some((entry) => {
        const base = String(entry.filename || '')
            .toLowerCase()
            .replace(/\.[a-z0-9]+$/, '');
        if (!base) return false;

        const tokens = new Set(base.split(/[^a-z0-9]+/).filter(Boolean));
        if (tokens.has(slugLower)) return true;
        return slugLower.length >= 4 && base.includes(slugLower);
    });
}