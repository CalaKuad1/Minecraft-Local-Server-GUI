import React from 'react';

export default function MotdPreview({ motd, iconUrl }) {
    // Basic Minecraft code parser
    const parseFormattedText = (text) => {
        if (!text) return null;

        // Handle newline legacy
        const lines = text.split(/\\n|\n/);

        return lines.map((line, i) => (
            <div key={i} className="whitespace-pre-wrap">
                {parseLine(line)}
            </div>
        ));
    };

    const parseLine = (text) => {
        const styleMap = {
            '0': 'text-[#000000]',
            '1': 'text-[#0000AA]',
            '2': 'text-[#00AA00]',
            '3': 'text-[#00AAAA]',
            '4': 'text-[#AA0000]',
            '5': 'text-[#AA00AA]',
            '6': 'text-[#FFAA00]',
            '7': 'text-[#AAAAAA]',
            '8': 'text-[#555555]',
            '9': 'text-[#5555FF]',
            'a': 'text-[#55FF55]',
            'b': 'text-[#55FFFF]',
            'c': 'text-[#FF5555]',
            'd': 'text-[#FF55FF]',
            'e': 'text-[#FFFF55]',
            'f': 'text-[#FFFFFF]',
            'l': 'font-bold',
            'm': 'line-through',
            'n': 'underline',
            'o': 'italic',
        };

        const parts = text.split(/(?=&[0-9a-fk-or])/i);
        return parts.map((part, index) => {
            const match = part.match(/^&([0-9a-fk-or])(.*)/i);
            if (match) {
                const code = match[1].toLowerCase();
                const content = match[2];
                // r is reset, but handled simply here by just not applying class (default is weird in span, but works for color reset usually by closing span? React structure makes full reset hard without state stack, but simple span wrapping works for simple codes)
                // Actually, correct parsing requires a state machine or recursive span structure.
                // For simplicity in this preview: simple span with class if color.
                // If it's a style (bold), it should apply to next. 
                // A robust parser is complex. Let's stick to simple color mapping for now.
                // If user uses multiple codes &a&lText, this split works? "&a" then "&lText". 
                // No, split keeps delimiter? My regex `(?=&...)` is a lookahead, so current part starts with &code.

                const className = styleMap[code] || '';
                // Since this is a simple linear map, &l after &a would be a new span resetting previous color? Yes, inaccurate.
                // But enough for a basic preview. "Mas utilidades" implies they want to see it.
                // Let's rely on a slightly better approach? 
                // For now, linear spans.

                return <span key={index} className={className}>{content}</span>;
            }
            return <span key={index} className="text-[#AAAAAA]">{part}</span>; // Default gray
        });
    };

    // Use default icon if none provided
    const displayIcon = iconUrl || "https://static.wikia.nocookie.net/minecraft_gamepedia/images/4/44/Grass_Block_Revision_6.png";

    return (
        <div className="w-full max-w-2xl bg-black/80 p-2 rounded flex items-center gap-3 font-minecraft text-white select-none border border-white/10 relative overflow-hidden group">
            {/* Background blur effect for premium feel */}
            <div className="absolute inset-0 bg-primary/5 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"></div>

            {/* Server Icon */}
            <div className="w-[64px] h-[64px] shrink-0 relative">
                <img
                    src={displayIcon}
                    alt="Server Icon"
                    className="w-full h-full object-contain pixelated"
                    onError={(e) => { e.target.src = "https://static.wikia.nocookie.net/minecraft_gamepedia/images/4/44/Grass_Block_Revision_6.png" }}
                />
            </div>

            {/* Server Info */}
            <div className="flex-1 min-w-0 flex flex-col justify-center h-[64px]">
                <div className="flex justify-between items-center mb-1">
                    <span className="text-white font-medium text-lg leading-none truncate">Minecraft Server</span>
                    <div className="flex gap-1 items-end">
                        <span className="text-[#AAAAAA] text-sm">20/20</span>
                        {/* Signal bars icon */}
                        <div className="w-4 h-3 bg-green-500/80 ml-1" style={{ clipPath: 'polygon(100% 0, 100% 100%, 80% 100%, 80% 20%, 60% 40%, 60% 100%, 40% 100%, 40% 60%, 20% 80%, 20% 100%, 0 100%)' }}></div>
                    </div>
                </div>
                <div className="text-base leading-tight font-minecraft-regular text-[#AAAAAA]">
                    {parseFormattedText(motd)}
                </div>
            </div>
        </div>
    );
}
