import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Eye, EyeOff, AlertCircle, ShieldAlert } from 'lucide-react';
import { WeaveLogo } from '../../components/ui/WeaveLogo';
import { SYNTHETIC_DEMO_ACCOUNTS, type DemoAccount } from '../../lib/syntheticSeed';
import { weaveApiClient, ApiClientError } from '../../lib/api-client';
import { useAuth } from '../../lib/auth';

const loginSchema = z.object({
  email: z.string().email('Enter a valid synthetic institutional or regulatory email address.'),
  password: z
    .string()
    .min(12, 'Password must be at least 12 characters.'),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export const LoginPage: React.FC = () => {
  const liveBackend = import.meta.env.VITE_API_MODE === 'live';
  const navigate = useNavigate();
  const { loginWithAccount } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: liveBackend ? '' : SYNTHETIC_DEMO_ACCOUNTS[0].email,
      password: liveBackend ? '' : 'synth-demo-session',
    },
  });

  const handleSelectDemoAccount = (acct: DemoAccount) => {
    setValue('email', acct.email, { shouldValidate: true });
    setValue('password', 'synth-demo-session', { shouldValidate: true });
    setAuthError(null);
  };

  const onSubmit = async (values: LoginFormValues) => {
    setAuthError(null);
    try {
      const response = await weaveApiClient.login(values.email, values.password);
      loginWithAccount(response.user, response.access_token);
      navigate('/app');
    } catch (err) {
      if (err instanceof ApiClientError) {
        setAuthError(`${err.message} (${err.code})`);
      } else {
        setAuthError('Unable to reach authentication endpoint. Verify development server status.');
      }
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F7F6F2] text-[#20241F]">
      {/* Persistent Synthetic Auth Disclosure */}
      <div className="bg-[#E9E7DF] border-b border-[#DEDDD5] px-6 py-2 text-xs text-[#20241F]">
        <div className="max-w-5xl mx-auto flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 font-medium">
            <ShieldAlert className="w-3.5 h-3.5 text-[#8E6218] shrink-0" />
            <span>
              {liveBackend
                ? 'SYNTHETIC BACKEND ACCOUNT — Authenticated by the local FastAPI service; not a production identity provider.'
                : 'SYNTHETIC DEMO AUTHENTICATION — Development-only session simulation using fixture accounts. Not production security.'}
            </span>
          </div>
          <Link to="/" className="underline hover:text-[#244C3A] font-mono">
            Return to public overview
          </Link>
        </div>
      </div>

      <main className="flex-1 max-w-5xl w-full mx-auto px-6 py-12 lg:py-20 grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
        {/* Left: Login Form */}
        <div className="lg:col-span-6 bg-white border border-[#DEDDD5] rounded-md p-6 sm:p-8 space-y-6">
          <div className="space-y-2">
            <Link to="/" className="inline-block">
              <WeaveLogo />
            </Link>
            <h1 className="font-display text-2xl font-bold text-[#20241F] pt-2">
              Sign in to WEAVE workspace
            </h1>
            <p className="text-xs text-[#686B65]">
              Access tokens are held strictly in memory and scoped by backend RBAC policy.
            </p>
          </div>

          {authError && (
            <div
              role="alert"
              className="p-3 bg-[#99322B]/10 border border-[#99322B]/30 rounded-md flex items-start gap-2 text-xs text-[#99322B]"
            >
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{authError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
            <div>
              <label
                htmlFor="login-email"
                className="block text-xs font-medium text-[#20241F] mb-1.5"
              >
                Institutional or Regulatory Email
              </label>
              <input
                id="login-email"
                type="email"
                autoComplete="username"
                {...register('email')}
                className="w-full px-3 py-2 text-sm bg-[#F7F6F2] border border-[#DEDDD5] rounded-md focus:outline-none focus:ring-2 focus:ring-[#244C3A]"
              />
              {errors.email && (
                <p role="alert" className="mt-1 text-xs text-[#99322B]">
                  {errors.email.message}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="login-password"
                className="block text-xs font-medium text-[#20241F] mb-1.5"
              >
                {liveBackend ? 'Account Password' : 'Session Passphrase (Synthetic Demo)'}
              </label>
              <div className="relative">
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  {...register('password')}
                  className="w-full pl-3 pr-10 py-2 text-sm font-mono bg-[#F7F6F2] border border-[#DEDDD5] rounded-md focus:outline-none focus:ring-2 focus:ring-[#244C3A]"
                />
                <button
                  type="button"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#686B65] hover:text-[#20241F] p-1"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
              {errors.password && (
                <p role="alert" className="mt-1 text-xs text-[#99322B]">
                  {errors.password.message}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-2.5 px-4 text-sm font-medium text-white bg-[#244C3A] hover:bg-[#193B2C] disabled:opacity-50 rounded-md transition-colors"
            >
              {isSubmitting ? 'Establishing session...' : 'Sign in to workspace'}
            </button>
          </form>
        </div>

        {/* Right: Synthetic Role Fixture Selector */}
        <div className="lg:col-span-6 space-y-4">
          {liveBackend ? (
            <div className="p-5 bg-white border border-[#DEDDD5] rounded-md space-y-2">
              <h2 className="font-display text-lg font-semibold text-[#20241F]">Local API accounts</h2>
              <p className="text-xs text-[#686B65]">
                Enter credentials provisioned in PostgreSQL with the backend administration CLI.
                Demo persona buttons are hidden because they do not authenticate against FastAPI.
              </p>
            </div>
          ) : (
          <>
          <div>
            <div className="text-xs font-mono uppercase tracking-widest text-[#686B65]">
              Synthetic Fixture Accounts (packages/fixtures)
            </div>
            <h2 className="mt-1 font-display text-lg font-semibold text-[#20241F]">
              Select a role persona to populate credentials
            </h2>
            <p className="text-xs text-[#686B65] mt-0.5">
              Each account demonstrates role-aware navigation, tenant isolation, and permission
              boundaries.
            </p>
          </div>

          <div className="space-y-2.5">
            {SYNTHETIC_DEMO_ACCOUNTS.map((acct) => (
              <button
                key={acct.id}
                type="button"
                onClick={() => handleSelectDemoAccount(acct)}
                className="w-full text-left p-4 bg-white border border-[#DEDDD5] hover:border-[#244C3A] rounded-md transition-colors space-y-1"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-[#20241F]">
                    {acct.name} · {acct.roleLabel}
                  </span>
                  <span className="font-mono text-[11px] text-[#244C3A]">{acct.role}</span>
                </div>
                <div className="font-mono text-xs text-[#686B65]">{acct.email}</div>
                <p className="text-xs text-[#686B65]">{acct.scopeDescription}</p>
              </button>
            ))}
          </div>
          </>
          )}
        </div>
      </main>
    </div>
  );
};
