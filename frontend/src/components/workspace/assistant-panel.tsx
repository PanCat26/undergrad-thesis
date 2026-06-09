"use client";

import * as React from "react";
import { toast } from "sonner";
import { Loader2, Plus, Send, Wrench, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { getErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { readSSE } from "@/lib/sse";
import { cn } from "@/lib/utils";
import type { ChatMessage, ChatSession, Citation, ProposedEdit } from "@/lib/types";

function tmpId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `tmp-${Math.random()}`;
}

function deriveTitle(content: string): string {
  const text = content.replace(/\s+/g, " ").trim();
  return text.length > 40 ? `${text.slice(0, 40).trimEnd()}…` : text || "New chat";
}

interface AssistantPanelProps {
  projectId: string;
  onViewSource: (sourceId: string) => void;
  onOpenFile: (path: string) => void;
  onEditApplied: (path: string) => void;
}

export function AssistantPanel({
  projectId,
  onViewSource,
  onOpenFile,
  onEditApplied,
}: AssistantPanelProps) {
  const { request, requestRaw } = useAuth();
  const base = `/api/projects/${projectId}/chat`;

  const [sessions, setSessions] = React.useState<ChatSession[]>([]);
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [messages, setMessages] = React.useState<ChatMessage[]>([]);
  const [input, setInput] = React.useState("");
  const [streaming, setStreaming] = React.useState(false);
  // The chosen mode before any session exists; a new session is created in this mode.
  const [pendingMode, setPendingMode] = React.useState<"qa" | "agentic">("qa");
  const bottomRef = React.useRef<HTMLDivElement>(null);
  const initRef = React.useRef(false);
  // Sessions created locally must not have their (empty) server history clobber
  // the optimistic messages of an in-flight send.
  const freshRef = React.useRef<Set<string>>(new Set());

  const createSession = React.useCallback(
    async (
      titleHint?: string,
      sessionMode: "qa" | "agentic" = "qa"
    ): Promise<ChatSession | null> => {
      try {
        const created = await request<ChatSession>(`${base}/sessions`, {
          method: "POST",
          body: { title: titleHint ?? "New chat", mode: sessionMode },
        });
        freshRef.current.add(created.id);
        setSessions((prev) => [...prev, created]);
        setActiveId(created.id);
        setMessages([]);
        return created;
      } catch (err) {
        toast.error(getErrorMessage(err, "Failed to create chat"));
        return null;
      }
    },
    [base, request]
  );

  // Load sessions once; ensure at least one exists so the first message is never lost.
  React.useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;
    (async () => {
      let list: ChatSession[] = [];
      try {
        list = await request<ChatSession[]>(`${base}/sessions`);
      } catch {
        // fall through to creating one
      }
      list = [...list].reverse(); // API returns newest-first; show oldest-first
      if (list.length === 0) {
        await createSession("Chat 1");
      } else {
        setSessions(list);
        setActiveId(list[list.length - 1].id);
      }
    })();
  }, [base, request, createSession]);

  // Load the active session's history (skipping freshly created, still-empty sessions).
  React.useEffect(() => {
    if (!activeId) {
      setMessages([]);
      return;
    }
    if (freshRef.current.has(activeId)) {
      freshRef.current.delete(activeId);
      return;
    }
    request<ChatMessage[]>(`${base}/sessions/${activeId}/messages`)
      .then(setMessages)
      .catch(() => setMessages([]));
  }, [activeId, base, request]);

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages]);

  const deleteSession = async (id: string) => {
    try {
      await request(`${base}/sessions/${id}`, { method: "DELETE" });
      setSessions((prev) => {
        const index = prev.findIndex((s) => s.id === id);
        const next = prev.filter((s) => s.id !== id);
        if (activeId === id) setActiveId(next[Math.max(0, index - 1)]?.id ?? null);
        return next;
      });
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to delete chat"));
    }
  };

  const send = async () => {
    const content = input.trim();
    if (!content || streaming) return;

    let sessionId = activeId;
    if (!sessionId) {
      const created = await createSession("New chat", mode);
      if (!created) return;
      sessionId = created.id;
    }

    // Name the chat after its first message (like Claude Code / Copilot).
    if (messages.length === 0) {
      const title = deriveTitle(content);
      setSessions((prev) => prev.map((s) => (s.id === sessionId ? { ...s, title } : s)));
    }

    setInput("");
    const assistantId = tmpId();
    setMessages((prev) => [
      ...prev,
      { id: tmpId(), role: "user", content, citations: null, created_at: "" },
      { id: assistantId, role: "assistant", content: "", citations: null, created_at: "" },
    ]);
    setStreaming(true);

    const patch = (fn: (m: ChatMessage) => ChatMessage) =>
      setMessages((prev) => prev.map((m) => (m.id === assistantId ? fn(m) : m)));

    try {
      const resp = await requestRaw(`${base}/sessions/${sessionId}/messages`, {
        method: "POST",
        body: { content },
      });
      if (!resp.ok) throw new Error("request failed");
      await readSSE(resp, (event) => {
        if (event.type === "final") {
          // Swap the streamed text for the final version (clean, renumbered citations).
          patch((m) => ({
            ...m,
            content: event.content,
            citations: event.citations as Citation[],
          }));
        } else if (event.type === "token") {
          patch((m) => ({ ...m, content: m.content + event.text }));
        } else if (event.type === "tool_call") {
          patch((m) => ({ ...m, steps: [...(m.steps ?? []), event.summary] }));
        } else if (event.type === "proposed_edit") {
          patch((m) => ({
            ...m,
            proposals: [
              ...(m.proposals ?? []),
              { path: event.path, diff: event.diff, content: event.content, status: "pending" },
            ],
          }));
        } else if (event.type === "error") {
          toast.error(event.message);
          patch((m) => ({ ...m, content: m.content || "Sorry, something went wrong." }));
        }
      });
    } catch (err) {
      toast.error(getErrorMessage(err, "The assistant failed to respond"));
      patch((m) => ({ ...m, content: m.content || "Sorry, something went wrong." }));
    } finally {
      setStreaming(false);
    }
  };

  const activeSession = sessions.find((s) => s.id === activeId) ?? null;
  const mode = activeSession?.mode ?? pendingMode;

  const switchMode = async (next: "qa" | "agentic") => {
    if (mode === next) return;
    if (!activeId) {
      // No conversation yet — remember the choice; the new session is created in this mode.
      setPendingMode(next);
      return;
    }
    setSessions((prev) => prev.map((s) => (s.id === activeId ? { ...s, mode: next } : s)));
    try {
      await request(`${base}/sessions/${activeId}`, { method: "PATCH", body: { mode: next } });
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to switch mode"));
    }
  };

  const setProposalStatus = (messageId: string, path: string, status: ProposedEdit["status"]) =>
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId
          ? { ...m, proposals: m.proposals?.map((p) => (p.path === path ? { ...p, status } : p)) }
          : m
      )
    );

  const applyEdit = async (messageId: string, proposal: ProposedEdit) => {
    try {
      await request(`/api/projects/${projectId}/files/apply`, {
        method: "POST",
        body: { path: proposal.path, content: proposal.content },
      });
      setProposalStatus(messageId, proposal.path, "applied");
      onEditApplied(proposal.path);
      toast.success(`Applied changes to ${proposal.path}`);
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to apply edit"));
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center gap-1 overflow-x-auto overflow-y-hidden border-b px-1.5 py-1">
        {sessions.map((s) => (
          <div
            key={s.id}
            onClick={() => setActiveId(s.id)}
            className={cn(
              "flex shrink-0 cursor-pointer items-center gap-1 rounded-md px-2 py-1 text-xs",
              activeId === s.id
                ? "bg-secondary text-secondary-foreground"
                : "text-muted-foreground hover:bg-accent"
            )}
          >
            <span className="max-w-[96px] truncate">{s.title}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                void deleteSession(s.id);
              }}
              className="rounded opacity-50 hover:opacity-100"
              aria-label="Close chat"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        ))}
        <Tooltip label="New chat">
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 shrink-0"
            aria-label="New chat"
            onClick={() => void createSession(undefined, mode)}
          >
            <Plus />
          </Button>
        </Tooltip>
      </div>

      <div className="flex shrink-0 items-center gap-1 border-b px-2 py-1.5">
        <ModeButton active={mode === "qa"} onClick={() => void switchMode("qa")}>
          Ask
        </ModeButton>
        <ModeButton active={mode === "agentic"} onClick={() => void switchMode("agentic")}>
          Agent
        </ModeButton>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-auto p-3">
        {messages.length === 0 ? (
          <p className="pt-8 text-center text-xs text-muted-foreground">
            Ask a question about your sources or draft.
          </p>
        ) : (
          messages.map((m) => (
            <MessageBubble
              key={m.id}
              message={m}
              streaming={streaming}
              onViewSource={onViewSource}
              onOpenFile={onOpenFile}
              onApprove={(p) => void applyEdit(m.id, p)}
              onReject={(p) => setProposalStatus(m.id, p.path, "rejected")}
            />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      <div className="shrink-0 border-t p-2">
        <div className="flex items-end gap-1.5">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            rows={2}
            placeholder="Ask"
            className="flex-1 resize-none rounded-md border border-input bg-transparent px-2 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
          <Button
            size="icon"
            className="h-8 w-8 shrink-0"
            aria-label="Send"
            disabled={streaming || !input.trim()}
            onClick={() => void send()}
          >
            {streaming ? <Loader2 className="animate-spin" /> : <Send />}
          </Button>
        </div>
      </div>
    </div>
  );
}

function ModeButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-md px-2.5 py-1 text-xs font-medium",
        active
          ? "bg-secondary text-secondary-foreground"
          : "text-muted-foreground hover:text-foreground"
      )}
    >
      {children}
    </button>
  );
}

function DiffView({ diff }: { diff: string }) {
  return (
    <pre className="mt-1 max-h-60 overflow-auto rounded border bg-background p-2 text-xs leading-relaxed">
      {diff.split("\n").map((line, i) => (
        <div
          key={i}
          className={cn(
            line.startsWith("+") && !line.startsWith("+++") && "text-green-600 dark:text-green-500",
            line.startsWith("-") && !line.startsWith("---") && "text-red-600 dark:text-red-500",
            line.startsWith("@@") && "text-muted-foreground"
          )}
        >
          {line || " "}
        </div>
      ))}
    </pre>
  );
}

function MessageBubble({
  message,
  streaming,
  onViewSource,
  onOpenFile,
  onApprove,
  onReject,
}: {
  message: ChatMessage;
  streaming: boolean;
  onViewSource: (sourceId: string) => void;
  onOpenFile: (path: string) => void;
  onApprove: (proposal: ProposedEdit) => void;
  onReject: (proposal: ProposedEdit) => void;
}) {
  const isUser = message.role === "user";
  const isEmptyAssistant = !isUser && message.content === "";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[90%] rounded-lg px-3 py-2 text-sm",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        )}
      >
        {!isUser && message.steps && message.steps.length > 0 && (
          <div className="mb-1.5 space-y-0.5">
            {message.steps.map((step, i) => (
              <div key={i} className="flex items-center gap-1 text-xs text-muted-foreground">
                <Wrench className="h-3 w-3 shrink-0" />
                <span className="truncate">{step}</span>
              </div>
            ))}
          </div>
        )}
        {isUser ? (
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        ) : isEmptyAssistant && streaming ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
        ) : isEmptyAssistant ? null : (
          <div className="prose prose-sm max-w-none break-words dark:prose-invert prose-p:my-1.5 prose-pre:my-1.5 prose-headings:my-2 prose-ul:my-1.5 prose-ol:my-1.5">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          </div>
        )}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 border-t border-border/50 pt-2">
            <p className="mb-1 text-xs font-medium text-muted-foreground">References</p>
            <div className="space-y-0.5">
              {message.citations.map((c) => (
                <button
                  key={c.index}
                  className="block text-left text-xs text-muted-foreground hover:text-foreground hover:underline"
                  onClick={() =>
                    c.kind === "source" && c.source_id
                      ? onViewSource(c.source_id)
                      : onOpenFile(c.filename)
                  }
                >
                  [{c.index}] {c.filename}
                  {c.loc?.page ? `, page ${c.loc.page}` : ""}
                </button>
              ))}
            </div>
          </div>
        )}
        {message.proposals?.map((proposal) => (
          <div key={proposal.path} className="mt-2 rounded-md border bg-background/60 p-2">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-xs font-medium">{proposal.path}</span>
              {proposal.status === "pending" ? (
                <div className="flex shrink-0 gap-1">
                  <Button size="sm" className="h-6 px-2 text-xs" onClick={() => onApprove(proposal)}>
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-6 px-2 text-xs"
                    onClick={() => onReject(proposal)}
                  >
                    Reject
                  </Button>
                </div>
              ) : (
                <span className="shrink-0 text-xs text-muted-foreground">{proposal.status}</span>
              )}
            </div>
            <DiffView diff={proposal.diff} />
          </div>
        ))}
      </div>
    </div>
  );
}
