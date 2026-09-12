"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { changePasswordAction } from "@/actions/change-password.action";
import { setPasswordAction } from "@/actions/set-password.action";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import {
  KeyRound,
  Lock,
  Eye,
  EyeOff,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  Info,
} from "lucide-react";

interface PasswordCardProps {
  hasPassword: boolean;
  isOAuthUser: boolean;
  providers: string[];
}

export function PasswordCard({
  hasPassword: initialHasPassword,
  isOAuthUser,
  providers,
}: PasswordCardProps) {
  const [hasPassword, setHasPassword] = useState(initialHasPassword);
  const [isPending, setIsPending] = useState(false);
  const router = useRouter();

  // Visibility toggles
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Form values
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [revokeSessions, setRevokeSessions] = useState(false);

  const providerNames = providers
    .filter((p) => p !== "credential")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" / ") || (isOAuthUser ? "Social Provider" : "Account");

  // Handle Set Password (For OAuth users who don't have a password yet)
  async function handleSetPassword(evt: React.FormEvent<HTMLFormElement>) {
    evt.preventDefault();

    if (!newPassword) {
      return toast.error("Please enter a new password");
    }

    if (newPassword.length < 6) {
      return toast.error("Password must be at least 6 characters long");
    }

    if (newPassword !== confirmPassword) {
      return toast.error("Passwords do not match");
    }

    setIsPending(true);

    try {
      const formData = new FormData();
      formData.append("newPassword", newPassword);
      formData.append("confirmPassword", confirmPassword);

      const result = await setPasswordAction(formData);

      if (result.error) {
        toast.error(result.error);
      } else {
        toast.success("Password created successfully! You can now sign in with your email and password.");
        setHasPassword(true);
        setNewPassword("");
        setConfirmPassword("");
        router.refresh();
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to set password");
    } finally {
      setIsPending(false);
    }
  }

  // Handle Change Password (For users who already have a password)
  async function handleChangePassword(evt: React.FormEvent<HTMLFormElement>) {
    evt.preventDefault();

    if (!currentPassword) {
      return toast.error("Please enter your current password");
    }

    if (!newPassword) {
      return toast.error("Please enter your new password");
    }

    if (newPassword.length < 6) {
      return toast.error("New password must be at least 6 characters long");
    }

    if (newPassword !== confirmPassword) {
      return toast.error("New passwords do not match");
    }

    setIsPending(true);

    try {
      const formData = new FormData();
      formData.append("currentPassword", currentPassword);
      formData.append("newPassword", newPassword);
      formData.append("confirmPassword", confirmPassword);
      if (revokeSessions) {
        formData.append("revokeOtherSessions", "true");
      }

      const result = await changePasswordAction(formData);

      if (result.error) {
        toast.error(result.error);
      } else {
        toast.success("Password changed successfully!");
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
        setRevokeSessions(false);
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to change password");
    } finally {
      setIsPending(false);
    }
  }

  return (
    <div className="space-y-4">
      {!hasPassword ? (
        /* SET NEW PASSWORD FLOW (OAuth Users without password) */
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-blue-50/70 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800/60 flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
            <div className="text-xs text-blue-900 dark:text-blue-200 leading-relaxed space-y-1">
              <p className="font-semibold text-sm text-blue-950 dark:text-blue-100">
                Create a Password for Direct Sign-In
              </p>
              <p>
                You registered or signed in using <strong>{providerNames}</strong>. You do not have a direct password set yet. Setting a password will allow you to sign in with your email directly in addition to {providerNames}.
              </p>
            </div>
          </div>

          <form onSubmit={handleSetPassword} className="space-y-4 max-w-md">
            {/* New Password */}
            <div className="space-y-2">
              <Label htmlFor="set-new-password" className="text-sm font-medium">
                New Password
              </Label>
              <div className="relative">
                <Input
                  id="set-new-password"
                  name="newPassword"
                  type={showNewPassword ? "text" : "password"}
                  placeholder="Enter at least 6 characters"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={6}
                  disabled={isPending}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors p-1"
                  tabIndex={-1}
                >
                  {showNewPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Confirm New Password */}
            <div className="space-y-2">
              <Label htmlFor="set-confirm-password" className="text-sm font-medium">
                Confirm New Password
              </Label>
              <div className="relative">
                <Input
                  id="set-confirm-password"
                  name="confirmPassword"
                  type={showConfirmPassword ? "text" : "password"}
                  placeholder="Re-enter new password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={6}
                  disabled={isPending}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors p-1"
                  tabIndex={-1}
                >
                  {showConfirmPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Password match indicator */}
            {newPassword && confirmPassword && (
              <div className="flex items-center gap-1.5 text-xs">
                {newPassword === confirmPassword ? (
                  <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Passwords match
                  </span>
                ) : (
                  <span className="text-destructive flex items-center gap-1 font-medium">
                    <ShieldAlert className="w-3.5 h-3.5" /> Passwords do not match
                  </span>
                )}
              </div>
            )}

            <Button
              type="submit"
              size="sm"
              disabled={
                isPending ||
                !newPassword ||
                !confirmPassword ||
                newPassword !== confirmPassword ||
                newPassword.length < 6
              }
              className="w-full sm:w-auto gap-2"
            >
              {isPending ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Setting Password...
                </>
              ) : (
                <>
                  <KeyRound className="w-3.5 h-3.5" />
                  Set New Password
                </>
              )}
            </Button>
          </form>
        </div>
      ) : (
        /* CHANGE PASSWORD FLOW (For users with an existing password) */
        <form onSubmit={handleChangePassword} className="space-y-4 max-w-md">
          {/* Current Password */}
          <div className="space-y-2">
            <Label htmlFor="current-password" className="text-sm font-medium">
              Current Password
            </Label>
            <div className="relative">
              <Input
                id="current-password"
                name="currentPassword"
                type={showCurrentPassword ? "text" : "password"}
                placeholder="Enter current password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                disabled={isPending}
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors p-1"
                tabIndex={-1}
              >
                {showCurrentPassword ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>

          {/* New Password */}
          <div className="space-y-2">
            <Label htmlFor="change-new-password" className="text-sm font-medium">
              New Password
            </Label>
            <div className="relative">
              <Input
                id="change-new-password"
                name="newPassword"
                type={showNewPassword ? "text" : "password"}
                placeholder="Enter at least 6 characters"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={6}
                disabled={isPending}
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors p-1"
                tabIndex={-1}
              >
                {showNewPassword ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>

          {/* Confirm New Password */}
          <div className="space-y-2">
            <Label htmlFor="change-confirm-password" className="text-sm font-medium">
              Confirm New Password
            </Label>
            <div className="relative">
              <Input
                id="change-confirm-password"
                name="confirmPassword"
                type={showConfirmPassword ? "text" : "password"}
                placeholder="Re-enter new password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={6}
                disabled={isPending}
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors p-1"
                tabIndex={-1}
              >
                {showConfirmPassword ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>

          {/* Password match indicator */}
          {newPassword && confirmPassword && (
            <div className="flex items-center gap-1.5 text-xs">
              {newPassword === confirmPassword ? (
                <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Passwords match
                </span>
              ) : (
                <span className="text-destructive flex items-center gap-1 font-medium">
                  <ShieldAlert className="w-3.5 h-3.5" /> Passwords do not match
                </span>
              )}
            </div>
          )}

          {/* Revoke other sessions */}
          <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer select-none">
            <input
              type="checkbox"
              checked={revokeSessions}
              onChange={(e) => setRevokeSessions(e.target.checked)}
              className="rounded border-border text-primary focus:ring-primary size-3.5"
            />
            Sign out of other devices after changing password
          </label>

          <Button
            type="submit"
            size="sm"
            disabled={
              isPending ||
              !currentPassword ||
              !newPassword ||
              !confirmPassword ||
              newPassword !== confirmPassword ||
              newPassword.length < 6
            }
            className="w-full sm:w-auto gap-2"
          >
            {isPending ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Changing Password...
              </>
            ) : (
              <>
                <ShieldCheck className="w-3.5 h-3.5" />
                Change Password
              </>
            )}
          </Button>
        </form>
      )}
    </div>
  );
}
