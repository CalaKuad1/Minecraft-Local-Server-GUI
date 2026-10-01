import clsx from 'clsx';
import { twMerge } from 'tailwind-merge';

// Joins class names and lets the last Tailwind utility win (`cn('px-4', 'px-2')` -> 'px-2').
export const cn = (...inputs) => twMerge(clsx(inputs));
