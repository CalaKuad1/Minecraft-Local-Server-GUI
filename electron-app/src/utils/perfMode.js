// "full" keeps the blur/grain effects; "lite" turns them off (see index.css).
const KEY = 'perfMode';

export function getPerfMode() {
    try {
        return localStorage.getItem(KEY) === 'lite' ? 'lite' : 'full';
    } catch {
        return 'full';
    }
}

export function applyPerfMode(mode) {
    document.documentElement.dataset.perf = mode === 'lite' ? 'lite' : 'full';
}

export function setPerfMode(mode) {
    try {
        localStorage.setItem(KEY, mode);
    } catch { /* storage unavailable: still apply for this session */ }
    applyPerfMode(mode);
}
