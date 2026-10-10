import type { Chat } from "../types";
import { timeAgo } from "../utils/time";

export function SideBar({ chats, selectedChatId, userEmail, onSelectChat, onNewChat, onDeleteChat, onOpenSettings }: {
    chats: Chat[];
    selectedChatId: number | null;
    userEmail: string;
    onSelectChat: (chat: Chat) => void;
    onNewChat: () => void;
    onDeleteChat: (chatId: number) => void;
    onOpenSettings: () => void;
}) {
    return (
        <div className="flex flex-col h-screen w-64 shrink-0 bg-gray-50 border-r border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-4">
                <img src="/logo.svg" alt="Document Q&A logo" className="w-7 h-7" />
                <h1 className="text-sm font-semibold">Document Q&A</h1>
            </div>

            <button
                onClick={onNewChat}
                className="w-full bg-blue-600 text-white rounded-full py-2 px-4 text-sm font-medium mb-4 hover:bg-blue-700"
            >
                New Chat
            </button>

            <p className="text-xs font-semibold text-gray-400 uppercase mb-2">Recent</p>

            {chats.length === 0 && (
                <p className="text-xs text-gray-400 px-2">No chats yet. Start one above.</p>
            )}

            <ul className="flex-1 overflow-y-auto space-y-1">
                {chats.map((chat) => (
                    <li
                        key={chat.id}
                        onClick={() => onSelectChat(chat)}
                        className={`group flex justify-between items-center gap-2 px-2 py-2 rounded-lg text-sm cursor-pointer ${
                            chat.id === selectedChatId ? "bg-blue-50 text-blue-700" : "hover:bg-gray-100"
                        }`}
                    >
                        <div className="min-w-0">
                            <p className="truncate">{chat.title}</p>
                            <p className="text-xs text-gray-400">
                                {chat.documents.length} {chat.documents.length === 1 ? "document" : "documents"} · {timeAgo(chat.updated_at)}
                            </p>
                        </div>
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                onDeleteChat(chat.id);
                            }}
                            aria-label="Delete chat"
                            className="text-gray-400 hover:text-red-600 opacity-0 group-hover:opacity-100 px-1"
                        >
                            ✕
                        </button>
                    </li>
                ))}
            </ul>

            <div className="flex items-center justify-between gap-2 pt-4 border-t border-gray-200">
                <div className="flex items-center gap-2 min-w-0">
                    <div className="w-8 h-8 shrink-0 rounded-full bg-blue-100 flex items-center justify-center text-xs font-medium">
                        {userEmail.slice(0, 2).toUpperCase()}
                    </div>
                    <span className="text-sm truncate">{userEmail}</span>
                </div>
                <button
                    onClick={onOpenSettings}
                    aria-label="Settings"
                    className="text-lg text-gray-500 hover:text-gray-700"
                >
                    ⚙
                </button>
            </div>
        </div>
    );
}