"use server";

import { auth } from "@/lib/auth";
import { uploadImageToCloudinary } from "@/lib/cloudinary";
import { prisma } from "@/lib/prisma";
import { headers } from "next/headers";

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif", "image/avif"];

export async function uploadAvatarAction(formData: FormData) {
  try {
    const headersList = await headers();
    const session = await auth.api.getSession({
      headers: headersList,
    });

    if (!session) {
      return { error: "You must be logged in to update your avatar" };
    }

    const isRemove = formData.get("remove") === "true";
    if (isRemove) {
      // Clear avatar
      await auth.api.updateUser({
        headers: headersList,
        body: {
          image: "",
        },
      });

      await prisma.user.update({
        where: { id: session.user.id },
        data: { image: null },
      });

      return { error: null, url: "" };
    }

    const file = formData.get("avatar") as File | null;
    const base64Data = formData.get("base64") as string | null;

    if (!file && !base64Data) {
      return { error: "No image file provided" };
    }

    let uploadResult: { url: string; publicId: string };

    if (file && file.size > 0) {
      if (file.size > MAX_FILE_SIZE) {
        return { error: "Image size exceeds 5MB limit. Please choose a smaller image." };
      }

      if (!ALLOWED_TYPES.includes(file.type)) {
        return { error: "Invalid image format. Supported formats: JPG, PNG, WebP, GIF, AVIF" };
      }

      const buffer = Buffer.from(await file.arrayBuffer());
      uploadResult = await uploadImageToCloudinary(buffer, "user_avatars");
    } else if (base64Data) {
      uploadResult = await uploadImageToCloudinary(base64Data, "user_avatars");
    } else {
      return { error: "Please select an image file" };
    }

    // Update user image in auth session and database
    await auth.api.updateUser({
      headers: headersList,
      body: {
        image: uploadResult.url,
      },
    });

    await prisma.user.update({
      where: { id: session.user.id },
      data: { image: uploadResult.url },
    });

    return { error: null, url: uploadResult.url };
  } catch (err: unknown) {
    console.error("Avatar upload error:", err);
    return {
      error: err instanceof Error ? err.message : "Failed to upload avatar to Cloudinary",
    };
  }
}
