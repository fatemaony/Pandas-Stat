"use server";

import { auth } from "@/lib/auth";
import { APIError } from "better-auth/api";
import { headers } from "next/headers";

export async function changePasswordAction(formData: FormData) {
  const currentPassword = String(formData.get("currentPassword") || "").trim();
  if (!currentPassword) {
    return { error: "Please enter your current password" };
  }

  const newPassword = String(formData.get("newPassword") || "").trim();
  if (!newPassword) {
    return { error: "Please enter your new password" };
  }

  if (newPassword.length < 6) {
    return { error: "New password must be at least 6 characters long" };
  }

  const confirmPassword = String(formData.get("confirmPassword") || "").trim();
  if (confirmPassword && newPassword !== confirmPassword) {
    return { error: "New passwords do not match. Please verify and try again." };
  }

  const revokeOtherSessions = formData.get("revokeOtherSessions") === "true";

  try {
    const headersList = await headers();
    await auth.api.changePassword({
      headers: headersList,
      body: {
        currentPassword,
        newPassword,
        revokeOtherSessions,
      },
    });

    return { error: null };
  } catch (err: unknown) {
    if (err instanceof APIError) {
      if (err.body?.code === "INVALID_PASSWORD") {
        return { error: "Incorrect current password. Please try again." };
      }
      return { error: err.message };
    }

    return {
      error: err instanceof Error ? err.message : "Failed to change password. Please try again.",
    };
  }
}