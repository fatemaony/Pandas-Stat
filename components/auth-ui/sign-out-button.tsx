"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { signOut } from "@/lib/auth-client";
import { useState } from "react";
import { LogOut, Loader2 } from "lucide-react";

interface SignOutButtonProps {
  className?: string;
  variant?: "default" | "outline" | "secondary" | "ghost" | "destructive" | "link";
  size?: "default" | "xs" | "sm" | "lg";
}

export const SignOutButton = ({
  className,
  variant = "destructive",
  size = "sm",
}: SignOutButtonProps) => {
  const router = useRouter();
  const [isPending, setIsPending] = useState(false);

  async function handleClick() {
    await signOut({
      fetchOptions: {
        onRequest: () => {
          setIsPending(true);
        },
        onResponse: () => {
          setIsPending(false);
        },
        onError: (ctx) => {
          toast.error(ctx.error?.message || "Failed to log out");
        },
        onSuccess: () => {
          toast.success("Logged out successfully");
          router.push("/auth/signin");
        },
      },
    });
  }

  return (
    <Button
      variant={variant}
      size={size}
      onClick={handleClick}
      disabled={isPending}
      className={className}
    >
      {isPending ? (
        <>
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          <span>Logging out...</span>
        </>
      ) : (
        <>
          <LogOut className="w-3.5 h-3.5" />
          <span>Log out</span>
        </>
      )}
    </Button>
  );
};