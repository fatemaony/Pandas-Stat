import Link from "next/link";
import { Button } from "./ui/button";
import { ArrowBigLeftIcon } from "lucide-react";

interface ReturnButtonProps {
  href: string;
  label: string;
  className?: string;
}

export const ReturnButton = ({
  href,
  label,
  className,
}: ReturnButtonProps) => {
  return (
    <Button asChild size="sm" variant="outline" className={className}>
      <Link className="flex items-center justify-start gap-1.5" href={href}>
        <ArrowBigLeftIcon className="h-4 w-4" />
        <span>{label}</span>
      </Link>
    </Button>
  );
};