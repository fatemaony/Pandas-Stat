import { v2 as cloudinary, type UploadApiResponse } from "cloudinary";

type CloudinaryUploadError = Error & {
  http_code?: number;
  name?: string;
};

const cloudName = process.env.CLOUDINARY_CLOUD_NAME;
const apiKey = process.env.CLOUDINARY_API_KEY;
const apiSecret = process.env.CLOUDINARY_API_SECRET;

// Configure Cloudinary using server-side credentials only
cloudinary.config({
  cloud_name: cloudName,
  api_key: apiKey,
  api_secret: apiSecret,
  secure: true,
});

export function isCloudinaryConfigured(): boolean {
  return Boolean(cloudName && apiKey && apiSecret);
}

export async function uploadImageToCloudinary(
  fileInput: string | Buffer,
  folder = "user_avatars"
): Promise<{ url: string; publicId: string }> {
  if (!isCloudinaryConfigured()) {
    throw new Error(
      "Cloudinary is not configured. Please set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET."
    );
  }

  let dataUri: string;

  if (typeof fileInput === "string") {
    // Already a data URI/base64 string
    dataUri = fileInput;
  } else {
    // Convert Buffer to data URI
    dataUri = `data:image/jpeg;base64,${fileInput.toString("base64")}`;
  }

  try {
    const result: UploadApiResponse = await cloudinary.uploader.upload(
      dataUri,
      {
        folder,
        resource_type: "image",
        transformation: [
          {
            width: 400,
            height: 400,
            crop: "fill",
            gravity: "face",
          },
          {
            quality: "auto",
            fetch_format: "auto",
          },
        ],
      }
    );

    return {
      url: result.secure_url,
      publicId: result.public_id,
    };
  } catch (error: unknown) {
    console.error("========== CLOUDINARY UPLOAD ERROR ==========");

    if (error instanceof Error) {
      console.error("Message:", error.message);
      console.error("Name:", error.name);
    }

    const uploadError = error as CloudinaryUploadError;
    if (uploadError.http_code) {
      console.error("HTTP code:", uploadError.http_code);
    }

    console.error("Full error:", error);
    console.error("==============================================");

    if (uploadError.http_code === 401 || uploadError.http_code === 403) {
      throw new Error(
        `Cloudinary rejected the upload (HTTP ${uploadError.http_code}). Verify that CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET belong to the active cloudinary cloud, and that the account allows image uploads.`
      );
    }

    throw error instanceof Error ? error : new Error("Cloudinary upload failed");
  }
}

export { cloudinary };