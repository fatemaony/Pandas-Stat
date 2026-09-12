"use server";

import { auth } from "@/lib/auth";
import { APIError } from "better-auth/api";
import { headers } from "next/headers";

export async function setPasswordAction(formData: FormData) {
  const newPassword = String(formData.get("newPassword") || "").trim();
  const confirmPassword = String(formData.get("confirmPassword") || "").trim();

  if (!newPassword) {
    return { error: "Please enter a new password" };
  }

  if (newPassword.length < 6) {
    return { error: "Password must be at least 6 characters long" };
  }

  if (newPassword !== confirmPassword) {
    return { error: "Passwords do not match. Please verify and try again." };
  }

  try {
    const headersList = await headers();
    await auth.api.setPassword({
      headers: headersList,
      body: {
        newPassword,
      },
    });

    return { error: null };
  } catch (err: unknown) {
    if (err instanceof APIError) {
      if (err.body?.code === "PASSWORD_ALREADY_SET") {
        return { error: "A password has already been set for this account. Please use Change Password instead." };
      }
      return { error: err.message };
    }

    return {
      error: err instanceof Error ? err.message : "An unexpected error occurred while setting password",
    };
  }
}
