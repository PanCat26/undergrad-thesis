"use client";

import * as React from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { getErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface LlmPreset {
  id: string;
  label: string;
}

const CUSTOM = "__custom__";

// next dev ⇒ "development"; the built prod image ⇒ "production".
const IS_DEV = process.env.NODE_ENV === "development";

const SELECT_CLASS =
  "flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

export function ModelCard() {
  const { user, request, updateLlm, testLlm } = useAuth();
  const [presets, setPresets] = React.useState<LlmPreset[]>([]);
  const [choice, setChoice] = React.useState<string>("");
  const [url, setUrl] = React.useState(user?.llm_base_url ?? "");
  const [model, setModel] = React.useState(user?.llm_base_url ? (user?.llm_model ?? "") : "");
  const [apiKey, setApiKey] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [testing, setTesting] = React.useState(false);
  const [testMsg, setTestMsg] = React.useState<{ ok: boolean; text: string } | null>(null);

  const isGuest = user?.is_guest ?? false;
  // Initialise the dropdown selection exactly once, so saving/refetching never resets the user's
  // in-progress choice (which made the custom menu flicker away).
  const initialised = React.useRef(false);

  React.useEffect(() => {
    if (initialised.current) return;
    request<LlmPreset[]>("/api/auth/llm-presets")
      .then((list) => {
        setPresets(list);
        if (!isGuest) {
          setChoice(user?.llm_base_url ? CUSTOM : (user?.llm_model ?? list[0]?.id ?? ""));
        }
        initialised.current = true;
      })
      .catch(() => undefined);
  }, [isGuest, request, user?.llm_base_url, user?.llm_model]);

  if (isGuest) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Model</CardTitle>
          <CardDescription>
            Create an account to choose which model powers the assistant.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <span className="rounded-md bg-muted px-3 py-1.5 text-sm font-medium">
            {presets[0]?.id ?? "gpt-4.1-mini"}
          </span>
        </CardContent>
      </Card>
    );
  }

  const choosePayload = () =>
    choice === CUSTOM
      ? { model: model.trim(), base_url: url.trim(), api_key: apiKey.trim() || null }
      : { model: choice, base_url: null, api_key: null };

  const save = async () => {
    if (choice === CUSTOM && (!url.trim() || !model.trim())) {
      toast.error("Enter an endpoint URL and a model name");
      return;
    }
    setSaving(true);
    try {
      await updateLlm(choosePayload());
      toast.success("Model updated");
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to update model"));
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    setTesting(true);
    setTestMsg(null);
    try {
      const result = await testLlm(choosePayload());
      setTestMsg(
        result.ok
          ? { ok: true, text: "Connection succeeded." }
          : { ok: false, text: result.error ?? "Connection failed." }
      );
    } catch (err) {
      setTestMsg({ ok: false, text: getErrorMessage(err, "Connection failed") });
    } finally {
      setTesting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Model</CardTitle>
        <CardDescription>
          Choose which chat model powers the assistant. You can use your own OpenAI-compatible
          endpoint (e.g. a local model via Ollama).
        </CardDescription>
        <CardDescription className="mt-2">
          {IS_DEV ? (
            <>
              For a local model, use <code>http://host.docker.internal:&lt;port&gt;</code>, not{" "}
              <code>127.0.0.1</code>. The backend runs in a container.
            </>
          ) : (
            <>
              A model on your own machine isn&apos;t reachable from the server directly: expose it
              with a tunnel (e.g. <code>cloudflared tunnel --url http://localhost:11434</code>) and
              paste the public URL.
            </>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="model-choice">Model</Label>
          <select
            id="model-choice"
            className={SELECT_CLASS}
            value={choice}
            onChange={(e) => {
              setChoice(e.target.value);
              setTestMsg(null);
            }}
          >
            {presets.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
            <option value={CUSTOM}>Local / custom model</option>
          </select>
        </div>

        {choice === CUSTOM && (
          <div className="space-y-4 rounded-md border border-dashed p-4">
            <div className="space-y-1.5">
              <Label htmlFor="model-url">Endpoint URL</Label>
              <Input
                id="model-url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="http://host.docker.internal:11434/v1"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="model-name">Model name</Label>
              <Input
                id="model-name"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="llama3.1"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="model-key">API key (optional)</Label>
              <PasswordInput
                id="model-key"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Leave empty for keyless local servers"
                autoComplete="off"
              />
            </div>
            <Button type="button" variant="outline" onClick={test} disabled={testing}>
              {testing && <Loader2 className="animate-spin" />}
              Test connection
            </Button>
            {testMsg && (
              <p className={testMsg.ok ? "text-sm text-green-600" : "text-sm text-destructive"}>
                {testMsg.text}
              </p>
            )}
          </div>
        )}

        <div className="flex items-center gap-2">
          <Button onClick={save} disabled={saving}>
            Save
          </Button>
          {saving && <Loader2 className="animate-spin text-muted-foreground" />}
        </div>
      </CardContent>
    </Card>
  );
}
