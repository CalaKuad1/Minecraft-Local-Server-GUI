import React from 'react';

// Turns player names in server log lines into links that open the player's
// card: chat ("<Steve> hi"), joins/leaves ("Steve joined the game") and
// logins ("Steve[/1.2.3.4:5678] logged in").
const PATTERN = /<([A-Za-z0-9_]{2,16})>|\b([A-Za-z0-9_]{2,16})(?= (?:joined|left) the game)|\b([A-Za-z0-9_]{2,16})(?=\[\/[^\]]*\] logged in)/g;

export function LinkifiedLog({ text, onOpenPlayer }) {
    if (!onOpenPlayer || typeof text !== 'string' || !text) return text ?? null;
    const parts = [];
    let last = 0;
    let m;
    PATTERN.lastIndex = 0;
    while ((m = PATTERN.exec(text)) !== null) {
        const name = m[1] || m[2] || m[3];
        const start = m.index + (m[1] ? 1 : 0); // skip the "<" of chat names
        if (start > last) parts.push(text.slice(last, start));
        parts.push(
            <button
                key={`${start}-${name}`}
                type="button"
                onClick={() => onOpenPlayer(name)}
                className="rounded px-0.5 font-semibold text-mint underline decoration-mint/40 underline-offset-2 hover:bg-grass/10 hover:decoration-mint"
            >
                {name}
            </button>,
        );
        last = start + name.length;
    }
    if (!parts.length) return text;
    if (last < text.length) parts.push(text.slice(last));
    return <>{parts}</>;
}

export default LinkifiedLog;
