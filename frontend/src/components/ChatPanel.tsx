import { useEffect, useRef, useState } from "react";
import type { Message, Chat } from "../types";
import { timeAgo } from "../utils/time";

const LOADING_WORDS = ["Thinking", "Processing", "Analyzing", "Generating", "Calculating", "Cross-referencing"];

export function ChatPanel({ selectedChat, messages, onSendMessage, isLoading, isUploading, onUploadDocument, onNewChat }: {
    selectedChat: Chat | null;
    messages: Message[];
    onSendMessage: (content: string) => void;
    isLoading: boolean;
    isUploading: boolean;
    onUploadDocument: (file: File) => void;
    onNewChat: () => void;
}) {
    const [inputText, setInputText] = useState<string>("");
    const [wordIndex, setWordIndex] = useState<number>(0);
    const bottomRef = useRef<HTMLDivElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const hasDocuments = (selectedChat?.documents.length ?? 0) > 0;
    const canType = !!selectedChat && hasDocuments;

    useEffect(() => {
        if (!isLoading) return;
        setWordIndex(0);
        const id = setInterval(() => {
            setWordIndex((current) => (current + 1) % LOADING_WORDS.length);
        }, 2500);
        return () => clearInterval(id);
    }, [isLoading]);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, isLoading, isUploading]);

    function handleSend() {
        if (canType && inputText.trim() !== "" && !isLoading) {
            onSendMessage(inputText);
            setInputText("");
        }
    }

    function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0];
        if (file) onUploadDocument(file);
        e.target.value = "";
    }

    const documentNames = Array.from(new Set(selectedChat?.documents ?? []));

    let placeholder = "Select a chat to start";
    if (selectedChat && !hasDocuments) placeholder = "Upload a document with + to start";
    if (canType) placeholder = "Ask a question about your documents";

    return (
        <div className="flex flex-col flex-1 h-screen bg-surface">
            <div className="flex justify-between items-center px-6 py-4 border-b border-gray-200">
                <h2 className="text-sm font-semibold truncate">{selectedChat?.title}</h2>
                <div className="flex gap-2 max-w-[60%] overflow-x-auto">
                    {documentNames.map((name) => (
                        <span
                            key={name}
                            title={name}
                            className="shrink-0 text-xs border border-gray-300 rounded-full px-3 py-1.5 text-gray-600 max-w-[220px] truncate"
                        >
                            📄 {name}
                        </span>
                    ))}
                </div>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
                {!selectedChat && (
                    <div className="h-full flex flex-col items-center justify-center text-center text-gray-400">
                        <p className="text-sm mb-3">Select a chat from the sidebar or start a new one.</p>
                        <button
                            onClick={onNewChat}
                            className="bg-blue-600 text-white rounded-full py-2 px-5 text-sm font-medium hover:bg-blue-700"
                        >
                            New chat
                        </button>
                    </div>
                )}

                {selectedChat && !hasDocuments && messages.length === 0 && !isUploading && (
                    <p className="text-center text-sm text-gray-400 mt-10">
                        This chat has no documents yet. Click + below to upload one.
                    </p>
                )}

                {canType && messages.length === 0 && !isLoading && (
                    <p className="text-center text-sm text-gray-400 mt-10">
                        Ask a question about your documents.
                    </p>
                )}

                {messages.map((message) => (
                    <div
                        key={message.id}
                        className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                        <div className={`max-w-[70%] flex flex-col ${message.role === "user" ? "items-end" : "items-start"}`}>
                            <div
                                className={
                                    message.role === "user"
                                        ? "bg-blue-600 text-white rounded-2xl px-4 py-3 text-sm"
                                        : "bg-surface border border-gray-200 rounded-2xl px-4 py-3 text-sm"
                                }
                            >
                                <p className="whitespace-pre-wrap">{message.content}</p>
                                {message.citations && message.citations.length > 0 && (
                                    <div className="mt-2 pt-2 border-t border-gray-100">
                                        <p className="text-[10px] font-semibold text-gray-400 uppercase mb-1">Source</p>
                                        <div className="flex gap-1 flex-wrap">
                                            {message.citations.map((citation, i) => (
                                                <span
                                                    key={i}
                                                    className="text-xs border border-gray-300 rounded-full px-2 py-0.5 text-gray-600"
                                                >
                                                    📄 {citation.document}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                            {message.created_at && (
                                <p className="text-[10px] text-gray-400 mt-1 px-1">{timeAgo(message.created_at)}</p>
                            )}
                        </div>
                    </div>
                ))}

                {isLoading && (
                    <div className="flex justify-start">
                        <div className="bg-surface border border-gray-200 rounded-2xl px-4 py-3 max-w-[70%] text-sm text-gray-400">
                            {LOADING_WORDS[wordIndex]}...
                        </div>
                    </div>
                )}

                {isUploading && (
                    <div className="flex justify-start">
                        <div className="bg-surface border border-gray-200 rounded-2xl px-4 py-3 max-w-[70%] text-sm text-gray-400">
                            Uploading and indexing your document...
                        </div>
                    </div>
                )}

                <div ref={bottomRef} />
            </div>

            <div className="flex items-center gap-2 px-6 py-4 border-t border-gray-200">
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.docx,.pptx,.txt"
                    onChange={handleFileChange}
                    className="hidden"
                />
                <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={!selectedChat || isUploading}
                    title="Upload a document to this chat"
                    className="w-8 h-8 rounded-full border border-gray-300 flex items-center justify-center text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                >
                    +
                </button>
                <input
                    type="text"
                    value={inputText}
                    disabled={!canType}
                    onChange={(e) => setInputText(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === "Enter") handleSend();
                    }}
                    placeholder={placeholder}
                    className="flex-1 border border-gray-300 rounded-full px-4 py-2 text-sm focus:outline-none focus:border-blue-500 disabled:bg-gray-50"
                />
                <button
                    onClick={handleSend}
                    disabled={!canType}
                    className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center hover:bg-blue-700 disabled:opacity-50"
                >
                    ↑
                </button>
            </div>
        </div>
    );
}