export function getBrowserWebSocketUrl(path: string): string {
  if (typeof window === "undefined") {
    return `ws://localhost:3000${path}`;
  }

  // Use environment variable for API URL if available
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || window.location.origin;
  const url = new URL(apiUrl);
  const protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${url.host}${path}`;
}

export function getBrowserApiUrl(path: string): string {
  if (typeof window === "undefined") {
    return path;
  }

  // Use environment variable for API URL if available
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || window.location.origin;
  return new URL(path, apiUrl).toString();
}
