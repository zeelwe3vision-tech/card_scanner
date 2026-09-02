import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function formatPhone(phone: string | null): string {
  if (!phone) return "—";
  return phone;
}

export function displayValue(value: string | null | undefined): string {
  return value && value.trim() !== "" ? value : "—";
}