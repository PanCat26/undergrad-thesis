"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { LogOut, User as UserIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tooltip } from "@/components/ui/tooltip";
import { useAuth } from "@/lib/auth";

export function AppHeader() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  const displayName = user?.is_guest ? "Guest" : (user?.email?.split("@")[0] ?? "Account");

  const doLogout = () => {
    logout();
    toast.success("You have been logged out");
    router.replace("/login");
  };

  const handleLogout = () => {
    if (user?.is_guest) {
      setConfirmOpen(true);
      return;
    }
    doLogout();
  };

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b px-6">
      <Link href="/projects" className="font-semibold">
        Evidentia Research Tool
      </Link>
      <div className="flex items-center gap-2">
        <span
          className="rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground"
          title={user?.is_guest ? undefined : (user?.email ?? undefined)}
        >
          {displayName}
        </span>
        <Tooltip label="Account">
          <Button variant="ghost" size="icon" asChild aria-label="Account">
            <Link href="/account">
              <UserIcon />
            </Link>
          </Button>
        </Tooltip>
        <Tooltip label="Log out">
          <Button variant="ghost" size="icon" onClick={handleLogout} aria-label="Log out">
            <LogOut />
          </Button>
        </Tooltip>
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Log out of your guest session?</DialogTitle>
            <DialogDescription>
              You are using a guest session, which is not saved. If you log out now you will lose
              access to your projects. Make sure you have finished your work before logging out.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              Stay
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setConfirmOpen(false);
                doLogout();
              }}
            >
              Log out
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </header>
  );
}
