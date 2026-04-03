export function getBrowserWebSocketUrl(path: string): string {
  if (typeof window === "undefined") {
    return `ws://localhost:3000${path}`;
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}

export function getBrowserApiUrl(path: string): string {
  if (typeof window === "undefined") {
    return path;
  }

  return new URL(path, window.location.origin).toString();
}
