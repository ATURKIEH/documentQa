import { useEffect, useRef, useState } from "react";
import { SideBar } from "./components/Sidebar";
import { ChatPanel } from "./components/ChatPanel";
import { LoginForm } from "./components/LoginForm";
import { SignupForm } from "./components/SignupForm";
import { NewChatModal } from "./components/NewChatModal";
import { SettingsModal } from "./components/SettingsModal";
import { API_URL } from "./config";
import type { Chat, Message } from "./types";

type Theme = "light" | "dark";

async function errorDetail(response: Response, fallback: string): Promise<string> {
  const body = await response.json().catch(() => null);
  return typeof body?.detail === "string" ? body.detail : fallback;
}

function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("token"));
  const [authView, setAuthView] = useState<"login" | "signup">("login");
  const [notice, setNotice] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>(() =>
    localStorage.getItem("theme") === "dark" ? "dark" : "light"
  );
  const [userEmail, setUserEmail] = useState<string>("");
  const [chats, setChats] = useState<Chat[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [showNewChat, setShowNewChat] = useState<boolean>(false);
  const [showSettings, setShowSettings] = useState<boolean>(false);
  const refreshInFlight = useRef<Promise<string | null> | null>(null);

  const selectedChat = chats.find((c) => c.id === selectedChatId) ?? null;

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("theme", theme);
  }, [theme]);

  function handleLogin(accessToken: string, refreshToken: string) {
    localStorage.setItem("token", accessToken);
    localStorage.setItem("refresh_token", refreshToken);
    setNotice(null);
    setToken(accessToken);
  }

  function handleLogout() {
    localStorage.removeItem("token");
    localStorage.removeItem("refresh_token");
    setToken(null);
    setUserEmail("");
    setChats([]);
    setSelectedChatId(null);
    setMessages([]);
    setShowNewChat(false);
    setShowSettings(false);
  }

  async function requestNewAccessToken(): Promise<string | null> {
    const refreshToken = localStorage.getItem("refresh_token");
    if (!refreshToken) return null;
    try {
      const response = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // must match the field name in your RefreshRequest schema
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) return null;
      const data = await response.json();
      localStorage.setItem("token", data.access_token);
      if (data.refresh_token) localStorage.setItem("refresh_token", data.refresh_token);
      return data.access_token;
    } catch {
      return null;
    }
  }

  // several requests can hit a 401 at once; they all share one refresh call
  function refreshAccessToken(): Promise<string | null> {
    if (!refreshInFlight.current) {
      refreshInFlight.current = requestNewAccessToken().finally(() => {
        refreshInFlight.current = null;
      });
    }
    return refreshInFlight.current;
  }

  async function authFetch(path: string, options: RequestInit = {}): Promise<Response> {
    function send(accessToken: string | null) {
      const headers = new Headers(options.headers);
      headers.set("Authorization", `Bearer ${accessToken}`);
      return fetch(`${API_URL}${path}`, { ...options, headers });
    }

    let response = await send(localStorage.getItem("token"));
    if (response.status === 401) {
      const newToken = await refreshAccessToken();
      if (newToken) response = await send(newToken);
    }
    if (response.status === 401) {
      handleLogout();
      throw new Error("Session expired. Please sign in again.");
    }
    return response;
  }

  // initial data after login
  useEffect(() => {
    if (!token) return;
    async function loadInitialData() {
      try {
        const [chatsRes, meRes] = await Promise.all([authFetch("/chats"), authFetch("/auth/me")]);
        if (chatsRes.ok) setChats(await chatsRes.json());
        if (meRes.ok) setUserEmail((await meRes.json()).email);
      } catch (error) {
        console.error("Failed to load initial data:", error);
      }
    }
    loadInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // messages for the selected chat
  useEffect(() => {
    if (!token || selectedChatId === null) return;
    const chatId = selectedChatId;
    let cancelled = false;
    setMessages([]);
    async function loadMessages() {
      try {
        const response = await authFetch(`/chats/${chatId}`);
        if (!response.ok) return;
        const data = await response.json();
        if (!cancelled) setMessages(data.messages);
      } catch (error) {
        console.error("Failed to load messages:", error);
      }
    }
    loadMessages();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedChatId, token]);

  async function sendMessage(content: string) {
    if (!selectedChat) return;
    const chatId = selectedChat.id;
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: "user", content, created_at: new Date().toISOString() },
    ]);
    setIsLoading(true);
    try {
      const response = await authFetch(`/chats/${chatId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      if (!response.ok) {
        throw new Error(await errorDetail(response, "Failed to send message."));
      }
      const data: Message = await response.json();
      setMessages((prev) => [...prev, data]);
      // move this chat to the top with a fresh timestamp
      setChats((prev) => {
        const current = prev.find((c) => c.id === chatId);
        if (!current) return prev;
        return [
          { ...current, updated_at: data.created_at ?? current.updated_at },
          ...prev.filter((c) => c.id !== chatId),
        ];
      });
    } catch (error) {
      console.error("Error sending message:", error);
      const text = error instanceof Error ? error.message : "Failed to send message.";
      setMessages((prev) => [...prev, { id: Date.now() + 1, role: "assistant", content: text }]);
    } finally {
      setIsLoading(false);
    }
  }

  async function createChat(title: string) {
    const response = await authFetch("/chats", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, document_ids: [] }),
    });
    if (!response.ok) {
      throw new Error(await errorDetail(response, "Could not create chat."));
    }
    const chat: Chat = await response.json();
    setChats((prev) => [chat, ...prev]);
    setSelectedChatId(chat.id);
    setShowNewChat(false);
  }

  async function deleteChat(chatId: number) {
    if (!window.confirm("Delete this chat?")) return;
    const response = await authFetch(`/chats/${chatId}`, { method: "DELETE" });
    if (!response.ok) return;
    setChats((prev) => prev.filter((c) => c.id !== chatId));
    if (selectedChatId === chatId) {
      setSelectedChatId(null);
      setMessages([]);
    }
  }

  async function uploadDocument(file: File) {
    if (!selectedChat) return;
    const chatId = selectedChat.id;
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file); // must match the UploadFile parameter name
      // no Content-Type header: the browser sets the multipart boundary itself
      const response = await authFetch(`/chats/${chatId}/documents`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(await errorDetail(response, "Upload failed."));
      }
      const updated: Chat = await response.json();
      setChats((prev) => prev.map((c) => (c.id === chatId ? updated : c)));
    } catch (error) {
      const text = error instanceof Error ? error.message : "Upload failed.";
      setMessages((prev) => [
        ...prev,
        { id: Date.now(), role: "assistant", content: `Upload failed: ${text}` },
      ]);
    } finally {
      setIsUploading(false);
    }
  }

  if (!token) {
    if (authView === "signup") {
      return (
        <SignupForm
          onSwitchToLogin={() => setAuthView("login")}
          onSignupSuccess={() => {
            setNotice("Account created. Please sign in.");
            setAuthView("login");
          }}
        />
      );
    }
    return (
      <LoginForm
        onLogin={handleLogin}
        onSwitchToSignup={() => setAuthView("signup")}
        notice={notice}
      />
    );
  }

  return (
    <div className="flex">
      <SideBar
        chats={chats}
        selectedChatId={selectedChatId}
        userEmail={userEmail}
        onSelectChat={(chat) => {
          if (!isLoading && !isUploading) setSelectedChatId(chat.id);
        }}
        onNewChat={() => setShowNewChat(true)}
        onDeleteChat={deleteChat}
        onOpenSettings={() => setShowSettings(true)}
      />
      <ChatPanel
        selectedChat={selectedChat}
        messages={messages}
        onSendMessage={sendMessage}
        isLoading={isLoading}
        isUploading={isUploading}
        onUploadDocument={uploadDocument}
        onNewChat={() => setShowNewChat(true)}
      />
      {showNewChat && <NewChatModal onCreate={createChat} onClose={() => setShowNewChat(false)} />}
      {showSettings && (
        <SettingsModal
          userEmail={userEmail}
          theme={theme}
          onThemeChange={setTheme}
          onLogout={handleLogout}
          onClose={() => setShowSettings(false)}
        />
      )}
    </div>
  );
}

export default App;