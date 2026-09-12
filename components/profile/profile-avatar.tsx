"use client";

import { useState, useRef } from "react";
import { uploadAvatarAction } from "@/actions/upload-avatar.action";
import { Button } from "@/components/ui/button";
import { Camera, Trash2, Loader2, Upload, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";

interface ProfileAvatarProps {
  initialImage: string | null;
  name: string;
}

export function ProfileAvatar({ initialImage, name }: ProfileAvatarProps) {
  const [imageUrl, setImageUrl] = useState<string>(initialImage || "");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const getInitials = (nameStr: string) => {
    if (!nameStr) return "U";
    const parts = nameStr.trim().split(" ");
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    }
    return nameStr.slice(0, 2).toUpperCase();
  };

  const handleFileSelect = async (file: File) => {
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      toast.error("Please select a valid image file (JPG, PNG, WebP)");
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      toast.error("Image file size exceeds 5MB. Please choose a smaller image.");
      return;
    }

    // Show instant preview
    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);
    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append("avatar", file);

      const result = await uploadAvatarAction(formData);

      if (result.error) {
        toast.error(result.error);
        setPreviewUrl(null);
      } else {
        setImageUrl(result.url || "");
        setPreviewUrl(null);
        toast.success("Profile picture updated successfully via Cloudinary!");
        router.refresh();
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to upload image");
      setPreviewUrl(null);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleRemovePhoto = async () => {
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append("remove", "true");

      const result = await uploadAvatarAction(formData);

      if (result.error) {
        toast.error(result.error);
      } else {
        setImageUrl("");
        setPreviewUrl(null);
        toast.success("Profile picture removed");
        router.refresh();
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to remove photo");
    } finally {
      setIsUploading(false);
    }
  };

  const displayImage = previewUrl || imageUrl;

  return (
    <div className="flex flex-col sm:flex-row items-center gap-6">
      {/* Avatar Container */}
      <div
        className={`relative group shrink-0 size-28 sm:size-32 rounded-2xl overflow-hidden border-2 transition-all duration-200 cursor-pointer shadow-md ${
          isDragging
            ? "border-primary ring-4 ring-primary/20 scale-105"
            : "border-border hover:border-primary/60"
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        title="Click or drag an image to upload"
      >
        {displayImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={displayImage}
            alt={name || "User Avatar"}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full bg-linear-to-br from-primary/10 via-primary/5 to-muted flex items-center justify-center text-primary font-bold text-2xl sm:text-3xl select-none">
            {getInitials(name)}
          </div>
        )}

        {/* Hover / Loading Overlay */}
        <div
          className={`absolute inset-0 bg-black/50 backdrop-blur-xs flex flex-col items-center justify-center gap-1 text-white text-xs transition-opacity duration-200 ${
            isUploading ? "opacity-100" : "opacity-0 group-hover:opacity-100"
          }`}
        >
          {isUploading ? (
            <>
              <Loader2 className="w-6 h-6 animate-spin text-white" />
              <span className="font-medium text-[11px]">Uploading...</span>
            </>
          ) : (
            <>
              <Camera className="w-5 h-5" />
              <span className="font-medium">Change</span>
            </>
          )}
        </div>

        {/* Hidden File Input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif,image/avif"
          className="hidden"
          onChange={handleInputChange}
          disabled={isUploading}
        />
      </div>

      {/* Action Controls & Info */}
      <div className="flex flex-col items-center sm:items-start text-center sm:text-left gap-2.5">
        <div>
          <h3 className="font-bold text-5xl text-base text-foreground flex items-center justify-center sm:justify-start gap-1.5">
            {name}
            <Sparkles className="w-3.5 h-3.5 text-primary/70" />
          </h3>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="text-xs h-8 gap-1.5 cursor-pointer shadow-xs"
          >
            {isUploading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Upload className="w-3.5 h-3.5" />
            )}
            {displayImage ? "Change Picture" : "Upload Picture"}
          </Button>

          {displayImage && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={handleRemovePhoto}
              disabled={isUploading}
              className="text-xs h-8 gap-1.5 text-destructive hover:text-destructive hover:bg-destructive/10 cursor-pointer"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Remove
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
