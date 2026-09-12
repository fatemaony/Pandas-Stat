"use client";

import { useState } from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { updateProfileAction } from "@/actions/update-profile.action";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import { Loader2, User, Mail, Check } from "lucide-react";

interface ProfileInfoFormProps {
  initialName: string;
  email: string;
}

export function ProfileInfoForm({
  initialName,
  email,
}: ProfileInfoFormProps) {
  const [name, setName] = useState(initialName);
  const [isPending, setIsPending] = useState(false);
  const router = useRouter();

  const isChanged = name.trim() !== initialName.trim();

  async function handleSubmit(evt: React.FormEvent<HTMLFormElement>) {
    evt.preventDefault();
    if (!name.trim()) {
      return toast.error("Please enter your name");
    }

    setIsPending(true);

    try {
      const formData = new FormData();
      formData.append("name", name.trim());

      const result = await updateProfileAction(formData);

      if (result.error) {
        toast.error(result.error);
      } else {
        toast.success("Username updated successfully!");
        if (result.name) setName(result.name);
        router.refresh();
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to update profile");
    } finally {
      setIsPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Username / Full Name */}
        <div className="space-y-2">
          <Label htmlFor="name" className="text-sm font-medium flex items-center gap-1.5">
            <User className="w-3.5 h-3.5 text-muted-foreground" />
            Username / Full Name
          </Label>
          <Input
            id="name"
            name="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Your name"
            required
            minLength={2}
            className="w-full"
            disabled={isPending}
          />
        </div>

        {/* Email (Readonly) */}
        <div className="space-y-2">
          <Label htmlFor="email" className="text-sm font-medium flex items-center gap-1.5">
            <Mail className="w-3.5 h-3.5 text-muted-foreground" />
            Email Address
          </Label>
          <Input
            id="email"
            type="email"
            value={email}
            readOnly
            disabled
            className="w-full bg-muted/50 cursor-not-allowed opacity-80"
          />
        </div>
      </div>

      <div className="flex justify-end pt-2">
        <Button
          type="submit"
          size="sm"
          disabled={isPending || !isChanged || !name.trim()}
          className="gap-1.5 font-medium transition-all shadow-xs"
        >
          {isPending ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Check className="w-3.5 h-3.5" />
              Save Changes
            </>
          )}
        </Button>
      </div>
    </form>
  );
}
