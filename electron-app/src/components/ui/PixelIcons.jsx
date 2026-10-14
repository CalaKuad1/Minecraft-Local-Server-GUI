// App icon set. The file keeps its old name so the ~20 components importing
// from './ui/PixelIcons' did not need touching when the pixel-art icons were
// replaced by Lucide's rounded line icons (they match the Cubi logo's soft
// corners). Export names are the ones the components already use.
import React from 'react';
import {
    LayoutDashboard as LLayoutDashboard, SquareTerminal, Settings as LSettings, Users as LUsers,
    Activity as LActivity, Globe as LGlobe, Package as LPackage, Plug as LPlug, Play as LPlay,
    Square as LSquare, Cpu as LCpu, HardDrive as LHardDrive, X as LX, ExternalLink as LExternalLink,
    FolderOpen as LFolderOpen, Clock as LClock, User as LUser, Shield as LShield, ShieldOff as LShieldOff,
    Ban as LBan, CircleCheck, Search as LSearch, Plus as LPlus, Trash2 as LTrash2, EllipsisVertical,
    Check as LCheck, FolderPlus as LFolderPlus, Archive as LArchive, RefreshCw as LRefreshCw, Save as LSave,
    Server as LServer, Monitor as LMonitor, Zap as LZap, CircuitBoard as LCircuitBoard, Palette as LPalette,
    Upload as LUpload, Send as LSend, Download as LDownload, ChevronRight as LChevronRight,
    ChevronDown as LChevronDown, ChevronUp as LChevronUp, Folder as LFolder, LoaderCircle, ArrowLeft as LArrowLeft,
    ArrowRight as LArrowRight, Box as LBox, TriangleAlert, Info as LInfo, Minus as LMinus, CircleAlert,
    Copy as LCopy, Pencil as LPencil, Star as LStar,
} from 'lucide-react';

// Shared defaults: 20px like the old set, a slightly lighter stroke so icons
// sit quietly next to text. Callers may still pass size/className/strokeWidth.
const wrap = (Icon) => {
    const Wrapped = ({ size = 20, strokeWidth = 1.9, ...props }) => (
        <Icon size={size} strokeWidth={strokeWidth} absoluteStrokeWidth={false} aria-hidden={props['aria-label'] ? undefined : true} {...props} />
    );
    Wrapped.displayName = Icon.displayName || 'Icon';
    return Wrapped;
};

export const LayoutDashboard = wrap(LLayoutDashboard);
export const Terminal = wrap(SquareTerminal);
export const SettingsIcon = wrap(LSettings);
export const Settings = wrap(LSettings);
export const Users = wrap(LUsers);
export const Activity = wrap(LActivity);
export const Globe = wrap(LGlobe);
export const Package = wrap(LPackage);
export const Plug = wrap(LPlug);
export const Play = wrap(LPlay);
export const Square = wrap(LSquare);
export const Cpu = wrap(LCpu);
export const HardDrive = wrap(LHardDrive);
export const X = wrap(LX);
export const ExternalLink = wrap(LExternalLink);
export const FolderOpen = wrap(LFolderOpen);
export const Clock = wrap(LClock);
export const User = wrap(LUser);
export const Shield = wrap(LShield);
export const ShieldOff = wrap(LShieldOff);
export const Ban = wrap(LBan);
export const CheckCircle = wrap(CircleCheck);
export const Search = wrap(LSearch);
export const Plus = wrap(LPlus);
export const Trash2 = wrap(LTrash2);
export const MoreVertical = wrap(EllipsisVertical);
export const Check = wrap(LCheck);
export const FolderPlus = wrap(LFolderPlus);
export const Archive = wrap(LArchive);
export const RefreshCw = wrap(LRefreshCw);
export const Save = wrap(LSave);
export const Server = wrap(LServer);
export const Monitor = wrap(LMonitor);
export const Zap = wrap(LZap);
export const CircuitBoard = wrap(LCircuitBoard);
export const Palette = wrap(LPalette);
export const Upload = wrap(LUpload);
export const Send = wrap(LSend);
export const Download = wrap(LDownload);
export const ChevronRight = wrap(LChevronRight);
export const ChevronDown = wrap(LChevronDown);
export const ChevronUp = wrap(LChevronUp);
export const Folder = wrap(LFolder);
export const Loader2 = wrap(LoaderCircle);
export const ArrowLeft = wrap(LArrowLeft);
export const ArrowRight = wrap(LArrowRight);
export const Box = wrap(LBox);
export const AlertTriangle = wrap(TriangleAlert);
export const Info = wrap(LInfo);
export const Minus = wrap(LMinus);
export const AlertCircle = wrap(CircleAlert);
export const Copy = wrap(LCopy);
export const Pencil = wrap(LPencil);
export const Star = wrap(LStar);

// Lucide dropped brand marks, so GitHub is drawn here (Simple Icons path).
export const Github = ({ size = 20, className = '', ...props }) => (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" className={className} aria-hidden="true" {...props}>
        <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
    </svg>
);
