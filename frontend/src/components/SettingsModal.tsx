type Theme = "light" | "dark";

export function SettingsModal({ userEmail, theme, onThemeChange, onLogout, onClose }: {
    userEmail: string;
    theme: Theme;
    onThemeChange: (theme: Theme) => void;
    onLogout: () => void;
    onClose: () => void;
}) {
    const themes: { value: Theme; label: string }[] = [
        { value: "light", label: "Light" },
        { value: "dark", label: "Dark" },
    ];

    return (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
            <div
                onClick={(e) => e.stopPropagation()}
                className="w-96 bg-surface rounded-2xl p-6 space-y-6 shadow-xl"
            >
                <div className="flex justify-between items-center">
                    <h2 className="text-base font-semibold">Settings</h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
                </div>

                <section className="space-y-2">
                    <p className="text-xs font-semibold text-gray-400 uppercase">Appearance</p>
                    <div className="flex gap-2">
                        {themes.map((t) => (
                            <button
                                key={t.value}
                                onClick={() => onThemeChange(t.value)}
                                className={`flex-1 py-2 text-sm rounded-full border ${
                                    theme === t.value
                                        ? "bg-blue-600 text-white border-blue-600"
                                        : "border-gray-300 text-gray-600 hover:bg-gray-50"
                                }`}
                            >
                                {t.label}
                            </button>
                        ))}
                    </div>
                </section>

                <section className="space-y-2">
                    <p className="text-xs font-semibold text-gray-400 uppercase">Account</p>
                    <p className="text-sm">{userEmail}</p>
                    <button
                        onClick={onLogout}
                        className="w-full border border-red-300 text-red-600 rounded-full py-2 text-sm hover:bg-red-50"
                    >
                        Log out
                    </button>
                </section>
            </div>
        </div>
    );
}