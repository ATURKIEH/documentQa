export type Chat = {
    id: number;
    title: string;
    documents: string[];
    updated_at: string;

};
export type Citation = {
    document: string;
};

export type Message = {
    id: number;
    role: "user" | "assistant";
    content: string;
    citations?: Citation[];
    created_at?: string;
};
