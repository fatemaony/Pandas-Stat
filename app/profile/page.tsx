import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { headers } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";
import { ReturnButton } from "@/components/return-button";
import { SignOutButton } from "@/components/auth-ui/sign-out-button";
import { Button } from "@/components/ui/button";
import { ProfileAvatar } from "@/components/profile/profile-avatar";
import { ProfileInfoForm } from "@/components/profile/profile-info-form";
import { PasswordCard } from "@/components/profile/password-card";
import { AccountBadges } from "@/components/profile/account-badges";
import {
  LayoutDashboard,
  Shield,
  User as UserIcon,
  KeyRound,
  Calendar,
  Lock,
} from "lucide-react";

export default async function ProfilePage() {
  const headersList = await headers();

  const session = await auth.api.getSession({
    headers: headersList,
  });

  if (!session) {
    redirect("/auth/signin");
  }

  // Fetch full user details and linked accounts from the database
  const [dbUser, accounts, fullPostAccess] = await Promise.all([
    prisma.user.findUnique({
      where: { id: session.user.id },
    }),
    prisma.account.findMany({
      where: { userId: session.user.id },
      select: {
        id: true,
        providerId: true,
        password: true,
        createdAt: true,
      },
    }),
    auth.api.userHasPermission({
      body: {
        userId: session.user.id,
        permissions: {
          posts: ["update", "delete"],
        },
      },
    }),
  ]);

  const user = dbUser || session.user;
  const isAdmin = user.role === "ADMIN";

  // Determine password & OAuth status
  const hasPassword = accounts.some(
    (acc) => acc.providerId === "credential" && !!acc.password
  );

  const isOAuthUser = accounts.some((acc) =>
    ["google", "github"].includes(acc.providerId.toLowerCase())
  );

  const providers = Array.from(
    new Set(accounts.map((acc) => acc.providerId.toLowerCase()))
  );

  // If no account records are linked yet, fallback to credential if email is present
  if (providers.length === 0 && user.email) {
    providers.push("credential");
  }

  const formattedJoinDate = user.createdAt
    ? new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      }).format(new Date(user.createdAt))
    : null;

  return (
    <div className="min-h-screen bg-muted/20 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Top Navigation Bar */}
        <header className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-2 border-b border-border">
          <div className="flex items-center gap-2">
            <ReturnButton href="/" label="Back to Home" />
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
            {isAdmin && (
              <Button
                size="sm"
                asChild
                className="gap-1.5 bg-black text-white shadow-xs"
              >
                <Link href="/admin/dashboard">
                  <LayoutDashboard className="w-4 h-4" />
                  Admin Dashboard
                </Link>
              </Button>
            )}

            <SignOutButton />
          </div>
        </header>

        {/* Main Grid: Profile Info & Security Settings */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

          {/* Card 1: Personal Information & Username Edit */}
          <section className="rounded-2xl border border-border bg-card p-6 shadow-xs space-y-5">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pt-2">
            {/* Avatar with Cloudinary upload */}
            <ProfileAvatar
              initialImage={user.image || null}
              name={user.name|| "User"}
            />
          </div>
            <div className="flex items-center gap-2.5 pb-3 border-b border-border">
              <div className="p-2 rounded-lg bg-primary/10 text-primary">
                <UserIcon className="w-5 h-5" />
              </div>
              <div>
                <h2 className="font-semibold text-lg text-foreground">
                  Personal Information
                </h2>
                <p className="text-xs text-muted-foreground">
                  Update your display name and view account details.
                </p>
              </div>
            </div>

            <ProfileInfoForm
              initialName={user.name || ""}
              email={user.email}
            />
          </section>

          {/* Card 2: Security & Password Management */}
          <section className="rounded-2xl border border-border bg-card p-6 shadow-xs space-y-8">
            <div className="flex items-center gap-2.5 pb-3 border-b border-border">
              <div className="p-2 rounded-lg font-semibold text-primary">
                {hasPassword ? (
                  <Lock className="w-5 h-5" />
                ) : (
                  <KeyRound className="w-5 h-5" />
                )}
              </div>
              <div>
                <h2 className="font-semibold text-lg text-foreground">
                  {hasPassword ? "Change Password" : "Set Account Password"}
                </h2>
                <p className="text-xs text-muted-foreground">
                  {hasPassword
                    ? "Manage and update your direct sign-in password."
                    : "Create a password for direct email sign-in."}
                </p>
              </div>
            </div>

            <PasswordCard
              hasPassword={hasPassword}
              isOAuthUser={isOAuthUser}
              providers={providers}
            />
          </section>
        </div>

        {/* Card 3: Permissions & Role Overview */}
        <section className="rounded-2xl border border-border bg-card p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between gap-4 pb-3 border-b border-border">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400">
                <Shield className="w-5 h-5" />
              </div>
              <div>
                <h2 className="font-semibold text-lg text-foreground">
                  Account Role & Permissions
                </h2>
                <p className="text-xs text-muted-foreground">
                  Access level and system privileges assigned to your account.
                </p>
              </div>
            </div>

            <span className="text-xs font-semibold px-2.5 py-1 rounded-md bg-muted text-muted-foreground uppercase tracking-wider">
              {user.role}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Button size="sm" variant="outline" className="text-xs cursor-default">
              Manage Own Posts
            </Button>
            <Button
              size="sm"
              variant={fullPostAccess.success ? "default" : "outline"}
              disabled={!fullPostAccess.success}
              className="text-xs"
            >
              Manage All Posts
            </Button>
          </div>
        </section>
      </div>
    </div>
  );
}