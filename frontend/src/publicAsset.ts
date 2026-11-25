export function publicAsset(path: string): string {
  if (/^(https?:|data:|blob:)/i.test(path) || path.startsWith("/media/")) {
    return path;
  }
  return `${import.meta.env.BASE_URL}${path.replace(/^\/+/, "")}`;
}
