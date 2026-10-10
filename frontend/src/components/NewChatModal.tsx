import { useState } from "react";

export function NewChatModal({ onCreate, onClose }: {
    onCreate: (title: string) => Promise<void>;
    onClose: () => void;
}) {
    const [title, setTitle] = useState<string>("");
    const [isCreating, setIsCreating] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        setError(null);
        setIsCreating(true);
        try {
            await onCreate(title.trim() || "New chat");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Could not create chat.");
            setIsCreating(false);
        }
    }

    return (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
            <form
                onSubmit={handleSubmit}
                onClick={(e) => e.stopPropagation()}
                className="w-96 bg-surface rounded-2xl p-6 space-y-4 shadow-xl"
            >
                <div className="flex justify-between items-center">
                    <h2 className="text-base font-semibold">New chat</h2>
                    <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
                </div>
                <input
                    autoFocus
                    type="text"
                    placeholder="Chat title (optional)"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    className="w-full border border-gray-300 rounded-full px-4 py-2 text-sm focus:outline-none focus:border-blue-500"
                />
                <p className="text-xs text-gray-400">You'll add documents inside the chat with the + button.</p>
                {error && <p className="text-sm text-red-600">{error}</p>}
                <div className="flex gap-2">
                    <button
                        type="button"
                        onClick={onClose}
                        className="flex-1 border border-gray-300 rounded-full py-2 text-sm hover:bg-gray-50"
                    >
                        Cancel
                    </button>
                    <button
                        type="submit"
                        disabled={isCreating}
                        className="flex-1 bg-blue-600 text-white rounded-full py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                    >
                        {isCreating ? "Creating..." : "Create chat"}
                    </button>
                </div>
            </form>
        </div>
    );
}