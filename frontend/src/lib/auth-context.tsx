import { createContext, useContext } from "react";
import type { User } from "./api";

export interface AuthContextType {
  user: User;
  onLogout: () => void;
}

export const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthContext.Provider");
  return ctx;
}
