import fabricLogo from '../../assets/engines/fabric.png';
import forgeLogo from '../../assets/engines/forge-anvil.png';
import neoforgeLogo from '../../assets/engines/neoforge.png';
import paperLogo from '../../assets/engines/Paper_JE2_BE2.webp';
import spigotLogo from '../../assets/engines/spigot.png';
import vanillaLogo from '../../assets/engines/vanilla.webp';

// Server types with their real project logos, shown in full color. `pixel`
// marks low-res pixel art that must be scaled without smoothing. The Forge
// mark is the anvil alone, lightened so it reads on the dark UI.
const ENGINES = {
    vanilla: { name: 'Vanilla', src: vanillaLogo, color: 'text-emerald-300', bg: 'bg-emerald-500/10', border: 'border-emerald-500/25' },
    paper: { name: 'Paper', src: paperLogo, pixel: true, color: 'text-sky-300', bg: 'bg-sky-500/10', border: 'border-sky-500/25' },
    fabric: { name: 'Fabric', src: fabricLogo, pixel: true, color: 'text-amber-200', bg: 'bg-amber-400/10', border: 'border-amber-400/25' },
    forge: { name: 'Forge', src: forgeLogo, color: 'text-slate-200', bg: 'bg-slate-400/10', border: 'border-slate-400/25' },
    neoforge: { name: 'NeoForge', src: neoforgeLogo, pixel: true, rounded: true, color: 'text-orange-300', bg: 'bg-orange-500/10', border: 'border-orange-500/25' },
    spigot: { name: 'Spigot', src: spigotLogo, color: 'text-yellow-300', bg: 'bg-yellow-500/10', border: 'border-yellow-500/25' },
};
const FALLBACK = { name: '', src: null, color: 'text-ink-dim', bg: 'bg-white/5', border: 'border-white/10' };

export function engineKey(type) {
    const t = (type || '').toLowerCase();
    // "neoforge" contains "forge": check it first.
    return ['neoforge', 'forge', 'fabric', 'paper', 'spigot', 'vanilla'].find((k) => t.includes(k)) || null;
}

export function engineInfo(type) {
    const key = engineKey(type);
    return key ? ENGINES[key] : FALLBACK;
}
