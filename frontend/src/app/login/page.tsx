"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type View = "auth" | "confirm" | "forgot" | "reset";

const EMAIL_PATTERN = "[^@\\s]+@[^@\\s]+\\.[^@\\s]+";
const EMAIL_TITLE = "Enter a complete email address, like name@example.com";
const PASSWORD_PATTERN = "(?=.*[a-z])(?=.*[A-Z])(?=.*\\d).{8,}";
const PASSWORD_HINT =
  "At least 8 characters, including an uppercase letter, a lowercase letter, and a number";

export default function LoginPage() {
  const auth = useAuth();
  const router = useRouter();

  const [view, setView] = React.useState<View>("auth");
  const [tab, setTab] = React.useState("login");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [code, setCode] = React.useState("");
  const [newPassword, setNewPassword] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    if (auth.status === "authenticated") router.replace("/projects");
  }, [auth.status, router]);

  const run = async (fn: () => Promise<void>) => {
    setLoading(true);
    try {
      await fn();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleGuest = () => run(() => auth.startGuest().then(() => router.push("/projects")));

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    run(() => auth.login(email, password).then(() => router.push("/projects")));
  };

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      await auth.register(email, password);
      toast.success("We sent a confirmation code to your email");
      setCode("");
      setView("confirm");
    });
  };

  const handleConfirm = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      await auth.confirm(email, code);
      toast.success("Account confirmed — you can now log in");
      setPassword("");
      setView("auth");
      setTab("login");
    });
  };

  const handleForgot = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      await auth.forgotPassword(email);
      toast.success("If the account exists, a reset code was sent");
      setCode("");
      setNewPassword("");
      setView("reset");
    });
  };

  const handleReset = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      await auth.resetPassword(email, code, newPassword);
      toast.success("Password reset — you can now log in");
      setPassword("");
      setView("auth");
      setTab("login");
    });
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Agentic Research Tool</CardTitle>
          <CardDescription>
            {view === "auth" && "Sign in or create an account to continue"}
            {view === "confirm" && "Enter the confirmation code sent to your email"}
            {view === "forgot" && "We will email you a code to reset your password"}
            {view === "reset" && "Enter the code and choose a new password"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {view === "auth" && (
            <Tabs value={tab} onValueChange={setTab}>
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="login">Log in</TabsTrigger>
                <TabsTrigger value="register">Register</TabsTrigger>
              </TabsList>

              <TabsContent value="login">
                <form onSubmit={handleLogin} className="space-y-4 pt-2">
                  <Field
                    id="login-email"
                    label="Email"
                    type="email"
                    value={email}
                    onChange={setEmail}
                    pattern={EMAIL_PATTERN}
                    title={EMAIL_TITLE}
                    autoComplete="email"
                  />
                  <Field
                    id="login-password"
                    label="Password"
                    type="password"
                    value={password}
                    onChange={setPassword}
                    autoComplete="current-password"
                  />
                  <SubmitButton loading={loading}>Log in</SubmitButton>
                  <button
                    type="button"
                    className="w-full text-center text-sm text-muted-foreground hover:underline"
                    onClick={() => setView("forgot")}
                  >
                    Forgot password?
                  </button>
                </form>
              </TabsContent>

              <TabsContent value="register">
                <form onSubmit={handleRegister} className="space-y-4 pt-2">
                  <Field
                    id="reg-email"
                    label="Email"
                    type="email"
                    value={email}
                    onChange={setEmail}
                    pattern={EMAIL_PATTERN}
                    title={EMAIL_TITLE}
                    autoComplete="email"
                  />
                  <Field
                    id="reg-password"
                    label="Password"
                    type="password"
                    value={password}
                    onChange={setPassword}
                    pattern={PASSWORD_PATTERN}
                    title={PASSWORD_HINT}
                    minLength={8}
                    hint={PASSWORD_HINT}
                    autoComplete="new-password"
                  />
                  <SubmitButton loading={loading}>Create account</SubmitButton>
                </form>
              </TabsContent>
            </Tabs>
          )}

          {view === "confirm" && (
            <form onSubmit={handleConfirm} className="space-y-4">
              <Field
                id="confirm-email"
                label="Email"
                type="email"
                value={email}
                onChange={setEmail}
                pattern={EMAIL_PATTERN}
                title={EMAIL_TITLE}
                autoComplete="email"
              />
              <Field
                id="confirm-code"
                label="Confirmation code"
                value={code}
                onChange={setCode}
                autoComplete="one-time-code"
              />
              <SubmitButton loading={loading}>Confirm account</SubmitButton>
              <BackButton onClick={() => setView("auth")} />
            </form>
          )}

          {view === "forgot" && (
            <form onSubmit={handleForgot} className="space-y-4">
              <Field
                id="forgot-email"
                label="Email"
                type="email"
                value={email}
                onChange={setEmail}
                pattern={EMAIL_PATTERN}
                title={EMAIL_TITLE}
                autoComplete="email"
              />
              <SubmitButton loading={loading}>Send reset code</SubmitButton>
              <BackButton onClick={() => setView("auth")} />
            </form>
          )}

          {view === "reset" && (
            <form onSubmit={handleReset} className="space-y-4">
              <Field
                id="reset-code"
                label="Reset code"
                value={code}
                onChange={setCode}
                autoComplete="one-time-code"
              />
              <Field
                id="reset-password"
                label="New password"
                type="password"
                value={newPassword}
                onChange={setNewPassword}
                pattern={PASSWORD_PATTERN}
                title={PASSWORD_HINT}
                minLength={8}
                hint={PASSWORD_HINT}
                autoComplete="new-password"
              />
              <SubmitButton loading={loading}>Set new password</SubmitButton>
              <BackButton onClick={() => setView("auth")} />
            </form>
          )}
        </CardContent>
      </Card>

      <Button variant="ghost" onClick={handleGuest} disabled={loading}>
        Continue as guest
      </Button>
    </div>
  );
}

function Field({
  id,
  label,
  value,
  onChange,
  type = "text",
  hint,
  pattern,
  title,
  minLength,
  autoComplete,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  hint?: string;
  pattern?: string;
  title?: string;
  minLength?: number;
  autoComplete?: string;
}) {
  const common = {
    id,
    value,
    required: true,
    pattern,
    title,
    minLength,
    autoComplete,
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => onChange(e.target.value),
  };
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {type === "password" ? <PasswordInput {...common} /> : <Input type={type} {...common} />}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function SubmitButton({ loading, children }: { loading: boolean; children: React.ReactNode }) {
  return (
    <Button type="submit" className="w-full" disabled={loading}>
      {loading && <Loader2 className="animate-spin" />}
      {children}
    </Button>
  );
}

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className="w-full text-center text-sm text-muted-foreground hover:underline"
      onClick={onClick}
    >
      Back
    </button>
  );
}
