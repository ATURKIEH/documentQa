export function timeAgo(iso: string): string {
    // treat timestamps without a timezone as UTC
    const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(iso);
    const then = new Date(hasZone ? iso : iso + "Z").getTime();
    const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));

    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    return new Date(then).toLocaleDateString();
}