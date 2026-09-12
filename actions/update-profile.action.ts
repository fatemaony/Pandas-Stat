"use server";

import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { normalizeName } from "@/lib/utils";
import { APIError } from "better-auth/api";
import { headers } from "next/headers";

export async function updateProfileAction(formData: FormData) {
  const rawName = String(formData.get("name") || "").trim();
  const name = normalizeName(rawName);

  if (!name) {
    return { error: "Please enter a valid username/name" };
  }

  if (name.length < 2) {
    return { error: "Name must be at least 2 characters long" };
  }

  try {
    const headersList = await headers();
    const session = await auth.api.getSession({
      headers: headersList,
    });

    if (!session) {
      return { error: "You must be logged in to update your profile" };
    }

    await auth.api.updateUser({
      headers: headersList,
      body: {
        name,
      },
    });

    await prisma.user.update({
      where: { id: session.user.id },
      data: { name },
    });

    return { error: null, name };
  } catch (err: unknown) {
    if (err instanceof APIError) {
      return { error: err.message };
    }

    return {
      error: err instanceof Error ? err.message : "Failed to update profile",
    };
  }
}
