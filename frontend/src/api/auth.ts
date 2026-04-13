import { useQuery } from "@tanstack/react-query";

export interface User {
  authenticated: boolean;
  email?: string;
  name?: string;
  pseudo?: string;
  picture?: string;
  avatar_url?: string;
  language?: string;
  is_admin?: boolean;
  user_id?: string;
}

export function getToken(): string | null {
  return localStorage.getItem("mcp_token");
}

export function setToken(token: string) {
  localStorage.setItem("mcp_token", token);
}

export function clearToken() {
  localStorage.removeItem("mcp_token");
}

export function useCurrentUser() {
  const token = getToken();
  return useQuery({
    queryKey: ["auth", "me", token],
    queryFn: async () => {
      if (!token) return { authenticated: false } as User;
      const resp = await fetch("/api/v1/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) return { authenticated: false } as User;
      return resp.json() as Promise<User>;
    },
  });
}
