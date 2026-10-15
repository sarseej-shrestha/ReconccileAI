import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
export function money(cents: number | string, currency = "USD") {
  const value = BigInt(cents);
  const negative = value < 0n;
  const absolute = negative ? -value : value;
  const whole = (absolute / 100n).toLocaleString("en-US");
  return `${negative ? "−" : ""}${currency} ${whole}.${(absolute % 100n).toString().padStart(2, "0")}`;
}
export const label = (value: string) =>
  value.replaceAll("_", " ").toLowerCase();
