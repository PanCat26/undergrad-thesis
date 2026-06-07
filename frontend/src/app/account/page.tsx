"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

import { AppHeader } from "@/components/app-header";
import { AuthGuard } from "@/components/auth-guard";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { getErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const PASSWORD_PATTERN = "(?=.*[a-z])(?=.*[A-Z])(?=.*\\d).{8,}";
const PASSWORD_HINT =
  "At least 8 characters, including an uppercase letter, a lowercase letter, and a number";

export default function AccountPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-col">
        <AppHeader />
        <main className="mx-auto w-full max-w-2xl flex-1 space-y-6 px-6 py-8">
          <h1 className="text-2xl font-semibold">Account</h1>
          <ModelCard />
          <AccountActions />
        </main>
      </div>
    </AuthGuard>
  );
}

function ModelCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Model</CardTitle>
        <CardDescription>Model selection will be configurable in a future release.</CardDescription>
      </CardHeader>
      <CardContent>
        <span className="rounded-md bg-muted px-3 py-1.5 text-sm font-medium">gpt-4o-mini</span>
      </CardContent>
    </Card>
  );
}

function AccountActions() {
  const { user } = useAuth();

  if (user?.is_guest) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Guest session</CardTitle>
          <CardDescription>
            You are using a guest session. Register an account to change your password or manage
            account settings.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <>
      <ChangePasswordCard />
      <DeleteAccountCard />
    </>
  );
}

function ChangePasswordCard() {
  const { changePassword } = useAuth();
  const [oldPassword, setOldPassword] = React.useState("");
  const [newPassword, setNewPassword] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await changePassword(oldPassword, newPassword);
      toast.success("Password changed");
      setOldPassword("");
      setNewPassword("");
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to change password"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Change password</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="old-password">Current password</Label>
            <PasswordInput
              id="old-password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new-password">New password</Label>
            <PasswordInput
              id="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              pattern={PASSWORD_PATTERN}
              title={PASSWORD_HINT}
              minLength={8}
              autoComplete="new-password"
              required
            />
            <p className="text-xs text-muted-foreground">{PASSWORD_HINT}</p>
          </div>
          <Button type="submit" disabled={loading}>
            {loading && <Loader2 className="animate-spin" />}
            Update password
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function DeleteAccountCard() {
  const { deleteAccount } = useAuth();
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(false);

  const confirm = async () => {
    setLoading(true);
    try {
      await deleteAccount();
      toast.success("Account deleted");
      router.replace("/login");
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to delete account"));
      setLoading(false);
    }
  };

  return (
    <Card className="border-destructive/40">
      <CardHeader>
        <CardTitle>Delete account</CardTitle>
        <CardDescription>
          Permanently delete your account and all of its projects. This cannot be undone.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button variant="destructive">Delete account</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete account</DialogTitle>
              <DialogDescription>
                This permanently deletes your account and all projects. This action cannot be
                undone.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)} disabled={loading}>
                Cancel
              </Button>
              <Button variant="destructive" onClick={confirm} disabled={loading}>
                {loading && <Loader2 className="animate-spin" />}
                Delete account
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
