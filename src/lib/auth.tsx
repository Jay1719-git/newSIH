import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import {
  SYNTHETIC_DEMO_ACCOUNTS,
  type DemoAccount,
} from './syntheticSeed';
import type { UserRole } from './weaveEngine';

const apiRoot = `${(import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')}/api/v1`;

// Access token kept strictly in memory per Section 19 (never localStorage/sessionStorage/URL)
let inMemoryAccessToken: string | null = null;

export function getInMemoryAccessToken(): string | null {
  return inMemoryAccessToken;
}

export function setInMemoryAccessToken(token: string | null): void {
  inMemoryAccessToken = token;
}

interface AuthContextValue {
  user: DemoAccount;
  isAuthenticated: boolean;
  isLoading: boolean;
  apiMode: 'mock' | 'live';
  switchRolePersona: (role: UserRole, institutionId?: string) => void;
  loginWithAccount: (account: DemoAccount, token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const liveMode = import.meta.env.VITE_API_MODE === 'live';
  const [user, setUser] = useState<DemoAccount>(SYNTHETIC_DEMO_ACCOUNTS[0]);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!liveMode);
  const [isLoading, setIsLoading] = useState<boolean>(liveMode);
  const apiMode: 'mock' | 'live' = liveMode ? 'live' : 'mock';

  useEffect(() => {
    if (!liveMode) {
      setInMemoryAccessToken('synth_mem_tok_mock_mode');
      setIsLoading(false);
      return;
    }
    let cancelled = false;
    const restoreSession = async () => {
      try {
        const refresh = await fetch(`${apiRoot}/auth/refresh`, {
          method: 'POST',
          credentials: 'same-origin',
        });
        if (!refresh.ok) return;
        const session = await refresh.json();
        if (typeof session.access_token !== 'string') return;
        const accountResponse = await fetch(`${apiRoot}/auth/me`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
          credentials: 'same-origin',
        });
        if (!accountResponse.ok || cancelled) return;
        const account = await accountResponse.json();
        setInMemoryAccessToken(session.access_token);
        setUser({
          ...account,
          institution_id: account.institution_id || undefined,
          institution_name: account.institution_name || undefined,
        });
        setIsAuthenticated(true);
      } catch {
        if (!cancelled) setIsAuthenticated(false);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, [liveMode]);

  useEffect(() => {
    const expireSession = () => {
      setInMemoryAccessToken(null);
      setIsAuthenticated(false);
    };
    window.addEventListener('weave:session-expired', expireSession);
    return () => window.removeEventListener('weave:session-expired', expireSession);
  }, []);

  const switchRolePersona = useCallback((role: UserRole, institutionId?: string) => {
    if (import.meta.env.VITE_API_MODE === 'live') return;
    const matched =
      SYNTHETIC_DEMO_ACCOUNTS.find((a) => a.role === role) || SYNTHETIC_DEMO_ACCOUNTS[0];
    const updated: DemoAccount = {
      ...matched,
      institution_id:
        institutionId ||
        matched.institution_id ||
        (role === 'institution_operator' || role === 'institution_admin'
          ? 'INST-KKR-101'
          : undefined),
    };
    setInMemoryAccessToken(`synth_mem_tok_${role}_${Date.now().toString(36)}`);
    setUser(updated);
    setIsAuthenticated(true);
    setIsLoading(false);
  }, []);

  const loginWithAccount = useCallback((account: DemoAccount, token: string) => {
    setInMemoryAccessToken(token);
    setUser(account);
    setIsAuthenticated(true);
    setIsLoading(false);
  }, []);

  const logout = useCallback(() => {
    const token = getInMemoryAccessToken();
    if (import.meta.env.VITE_API_MODE === 'live' && token) {
      void fetch(`${apiRoot}/auth/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'same-origin',
      });
    }
    setInMemoryAccessToken(null);
    setIsAuthenticated(false);
    setIsLoading(false);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isLoading,
        apiMode,
        switchRolePersona,
        loginWithAccount,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
