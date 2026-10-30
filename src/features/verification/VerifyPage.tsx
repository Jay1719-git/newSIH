import React, { useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  ArrowLeft,
  ShieldCheck,
} from 'lucide-react';
import { WeaveLogo } from '../../components/ui/WeaveLogo';
import { weaveApiClient, weaveQueryKeys, ApiClientError } from '../../lib/api-client';
import { useAuth } from '../../lib/auth';

export const VerifyPage: React.FC = () => {
  const { apiMode } = useAuth();
  const { token = 'att-2026-901' } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const [tokenInput, setTokenInput] = useState(token);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: weaveQueryKeys.verifyToken(token),
    queryFn: () => weaveApiClient.verifyTokenPublic(token),
    retry: false,
    enabled: apiMode === 'mock',
  });

  const handleTokenSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleaned = tokenInput.trim();
    if (cleaned) {
      navigate(`/verify/${encodeURIComponent(cleaned)}`);
    }
  };

  const opaqueVerifyUrl = `https://weave.synth.edu/verify/${encodeURIComponent(token)}`;

  if (apiMode === 'live') {
    return (
      <main className="min-h-screen bg-[#F7F6F2] text-[#20241F] p-8">
        <div role="status" className="max-w-2xl mx-auto bg-white border border-[#DEDDD5] rounded-md p-6 space-y-3">
          <h1 className="font-display text-xl font-semibold">Public verification unavailable</h1>
          <p className="text-sm text-[#686B65]">
            The current FastAPI contract does not provide a public QR or attestation verification route. This request was not checked against an official service.
          </p>
          <Link to="/" className="text-sm text-[#244C3A] underline">Return to WEAVE</Link>
        </div>
      </main>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#F7F6F2] text-[#20241F]">
      {/* Top Bar */}
      <header className="bg-white border-b border-[#DEDDD5] px-6 h-16 flex items-center justify-between gap-8">
        <Link to="/" className="shrink-0">
          <WeaveLogo />
        </Link>
        <div className="text-xs font-mono text-[#686B65] hidden sm:block">
          PUBLIC CREDENTIAL VERIFICATION PORTAL · /verify/:token
        </div>
        <Link
          to="/app"
          className="px-3.5 py-1.5 text-xs font-medium text-[#20241F] border border-[#DEDDD5] rounded-md hover:bg-[#F0EFE9] transition-colors whitespace-nowrap shrink-0"
        >
          Open workspace
        </Link>
      </header>

      {/* Mandatory Disclaimer Banner */}
      <div className="bg-[#E9E7DF] border-b border-[#DEDDD5] px-6 py-2.5 text-xs text-[#20241F]">
        <div className="max-w-4xl mx-auto flex flex-wrap items-center justify-between gap-2">
          <span className="font-medium">
            Platform-issued enrolment attestation. Not an official government credential.
          </span>
          <span className="font-mono text-[11px] text-[#686B65]">
            SYNTHETIC DATA — DEMONSTRATION ONLY
          </span>
        </div>
      </div>

      <main className="flex-1 max-w-4xl w-full mx-auto px-6 py-10 space-y-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <Link
              to="/"
              className="inline-flex items-center gap-1.5 text-xs text-[#686B65] hover:text-[#20241F] mb-2"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to WEAVE overview</span>
            </Link>
            <h1 className="font-display text-2xl font-bold text-[#20241F]">
              Enrolment Attestation Verification
            </h1>
          </div>

          {/* Quick Token Switcher for Testing Valid / Revoked / Expired / Unknown States */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-[#686B65]">Sample tokens:</span>
            <Link
              to="/verify/att-2026-901"
              className={`px-2.5 py-1 rounded-sm font-mono border ${
                token.toLowerCase() === 'att-2026-901'
                  ? 'bg-[#244C3A] text-white border-[#244C3A]'
                  : 'bg-white text-[#20241F] border-[#DEDDD5]'
              }`}
            >
              Valid (att-2026-901)
            </Link>
            <Link
              to="/verify/att-2026-884"
              className={`px-2.5 py-1 rounded-sm font-mono border ${
                token.toLowerCase() === 'att-2026-884'
                  ? 'bg-[#244C3A] text-white border-[#244C3A]'
                  : 'bg-white text-[#20241F] border-[#DEDDD5]'
              }`}
            >
              Revoked (att-2026-884)
            </Link>
            <Link
              to="/verify/att-2025-772"
              className={`px-2.5 py-1 rounded-sm font-mono border ${
                token.toLowerCase() === 'att-2025-772'
                  ? 'bg-[#244C3A] text-white border-[#244C3A]'
                  : 'bg-white text-[#20241F] border-[#DEDDD5]'
              }`}
            >
              Expired (att-2025-772)
            </Link>
            <Link
              to="/verify/att-unknown-000"
              className={`px-2.5 py-1 rounded-sm font-mono border ${
                token.toLowerCase() === 'att-unknown-000'
                  ? 'bg-[#244C3A] text-white border-[#244C3A]'
                  : 'bg-white text-[#20241F] border-[#DEDDD5]'
              }`}
            >
              Unknown Token
            </Link>
          </div>
        </div>

        {/* Lookup Bar */}
        <form
          onSubmit={handleTokenSubmit}
          className="bg-white border border-[#DEDDD5] rounded-md p-4 flex flex-col sm:flex-row gap-3"
        >
          <label htmlFor="verify-token-input" className="sr-only">
            Verification Token
          </label>
          <input
            id="verify-token-input"
            type="text"
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            placeholder="Enter opaque verification token (e.g. att-2026-901)..."
            className="flex-1 px-3 py-2 text-xs font-mono bg-[#F7F6F2] border border-[#DEDDD5] rounded-md focus:outline-none focus:ring-2 focus:ring-[#244C3A]"
          />
          <button
            type="submit"
            className="px-4 py-2 text-xs font-medium text-white bg-[#244C3A] hover:bg-[#193B2C] rounded-md transition-colors whitespace-nowrap shrink-0"
          >
            Check Token
          </button>
        </form>

        {/* Loading Skeleton State */}
        {isLoading && (
          <div
            role="status"
            aria-label="Verifying attestation token"
            className="bg-white border border-[#DEDDD5] rounded-md p-6 space-y-4 animate-pulse"
          >
            <div className="h-5 w-48 bg-[#E9E7DF] rounded-sm" />
            <div className="h-4 w-3/4 bg-[#F0EFE9] rounded-sm" />
            <div className="grid grid-cols-2 gap-4 pt-4">
              <div className="h-16 bg-[#F0EFE9] rounded-sm" />
              <div className="h-16 bg-[#F0EFE9] rounded-sm" />
            </div>
          </div>
        )}

        {/* Error / Invalid Token State */}
        {isError && (
          <div
            role="alert"
            className="bg-white border border-[#99322B] rounded-md p-6 space-y-4"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-2 text-[#99322B] font-display font-semibold text-base">
                <XCircle className="w-5 h-5 shrink-0" />
                <span>
                  {error instanceof ApiClientError && error.status === 404
                    ? 'Invalid or Unknown Verification Token'
                    : 'Verification Service Error'}
                </span>
              </div>
              <button
                type="button"
                onClick={() => refetch()}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[#20241F] bg-[#F7F6F2] border border-[#DEDDD5] rounded-md hover:bg-[#E9E7DF]"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry</span>
              </button>
            </div>
            <p className="text-xs text-[#686B65]">
              {error instanceof Error
                ? error.message
                : 'Unable to verify token against backend registry.'}
            </p>
          </div>
        )}

        {/* Verified / Expired / Revoked Result Card */}
        {!isLoading && !isError && data && (
          <div className="bg-white border border-[#DEDDD5] rounded-md overflow-hidden">
            {/* Status Header */}
            <div
              className={`p-6 border-b border-[#DEDDD5] flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
                data.verification.valid ? 'bg-[#1E563B]/8' : 'bg-[#99322B]/8'
              }`}
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2 font-mono text-xs font-semibold">
                  {data.verification.valid ? (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-[#1E563B]" />
                      <span className="text-[#1E563B]">
                        {data.verification.status_code} · VALID CREDENTIAL
                      </span>
                    </>
                  ) : data.attestation.status === 'EXPIRED' ? (
                    <>
                      <AlertTriangle className="w-4 h-4 text-[#8E6218]" />
                      <span className="text-[#8E6218]">
                        {data.verification.status_code} · EXPIRED CREDENTIAL
                      </span>
                    </>
                  ) : (
                    <>
                      <XCircle className="w-4 h-4 text-[#99322B]" />
                      <span className="text-[#99322B]">
                        {data.verification.status_code} · REVOKED OR INVALID
                      </span>
                    </>
                  )}
                </div>
                <p className="text-sm text-[#20241F]">{data.verification.reason}</p>
              </div>

              <div className="text-right font-mono text-xs text-[#686B65] shrink-0">
                <div>Token: {data.attestation.id}</div>
                <div>Status: {data.attestation.status}</div>
              </div>
            </div>

            {/* Authorized Minimal-Disclosure Claims */}
            <div className="p-6 grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
              <div className="md:col-span-8 space-y-4">
                <h2 className="font-display text-sm font-semibold text-[#20241F]">
                  Authorized Minimal-Disclosure Claims (Consent {data.attestation.consent_id})
                </h2>

                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs border-t border-[#DEDDD5] pt-4">
                  <div>
                    <dt className="text-[#686B65]">Issuing Platform Authority</dt>
                    <dd className="font-medium text-[#20241F] mt-0.5">
                      {data.attestation.issuer}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[#686B65]">Enrolling Institution</dt>
                    <dd className="font-medium text-[#20241F] mt-0.5">
                      {data.attestation.institution_name}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[#686B65]">Protected APAAR Reference</dt>
                    <dd className="font-mono font-semibold text-[#20241F] mt-0.5 tabular-nums">
                      {data.attestation.apaar_masked} (Full ID Never Disclosed)
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[#686B65]">Institutional Student Ref</dt>
                    <dd className="font-mono text-[#20241F] mt-0.5 tabular-nums">
                      {data.attestation.student_ref}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[#686B65]">Sanctioned Program &amp; Year</dt>
                    <dd className="font-mono text-[#20241F] mt-0.5 tabular-nums">
                      {data.attestation.program_code} · AY {data.attestation.enrollment_year}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[#686B65]">Authorized Purpose</dt>
                    <dd className="text-[#20241F] mt-0.5">{data.attestation.purpose}</dd>
                  </div>
                  <div>
                    <dt className="text-[#686B65]">Issued Timestamp</dt>
                    <dd className="font-mono text-[#20241F] mt-0.5 tabular-nums">
                      {data.attestation.issued_at.slice(0, 10)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[#686B65]">Expiry Timestamp</dt>
                    <dd className="font-mono text-[#20241F] mt-0.5 tabular-nums">
                      {data.attestation.expires_at.slice(0, 10)}
                    </dd>
                  </div>
                </dl>

                {/* Cryptographic Verification Breakdown */}
                <div className="pt-4 border-t border-[#DEDDD5] space-y-2 text-xs">
                  <div className="font-semibold text-[#20241F] flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-[#244C3A]" />
                    <span>Cryptographic &amp; Lifecycle Checks</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 font-mono text-[11px]">
                    <div className="p-2.5 bg-[#F7F6F2] border border-[#DEDDD5] rounded-sm">
                      Signature: {data.verification.signature_match ? 'MATCH' : 'MISMATCH'}
                    </div>
                    <div className="p-2.5 bg-[#F7F6F2] border border-[#DEDDD5] rounded-sm">
                      Revocation: {data.verification.not_revoked ? 'UNREVOKED' : 'REVOKED'}
                    </div>
                    <div className="p-2.5 bg-[#F7F6F2] border border-[#DEDDD5] rounded-sm">
                      Validity Window: {data.verification.not_expired ? 'ACTIVE' : 'EXPIRED'}
                    </div>
                  </div>
                  <div className="p-2.5 bg-[#F7F6F2] border border-[#DEDDD5] rounded-sm font-mono text-[11px] text-[#686B65] break-all">
                    Key ID: {data.attestation.ed25519_key_id} · Sig:{' '}
                    {data.attestation.ed25519_signature}
                  </div>
                </div>
              </div>

              {/* Opaque Verification QR Matrix Representation */}
              <div className="md:col-span-4 bg-[#F7F6F2] border border-[#DEDDD5] rounded-md p-4 space-y-3">
                <div className="text-xs font-semibold text-[#20241F]">
                  Opaque Verification QR Reference
                </div>
                <div className="bg-white border border-[#DEDDD5] p-4 rounded-sm flex items-center justify-center">
                  <svg
                    width="128"
                    height="128"
                    viewBox="0 0 64 64"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                    role="img"
                    aria-label={`QR code encoding opaque verification URL ${opaqueVerifyUrl}`}
                  >
                    <rect width="64" height="64" fill="#FFFFFF" />
                    <rect x="4" y="4" width="18" height="18" stroke="#20241F" strokeWidth="3" />
                    <rect x="9" y="9" width="8" height="8" fill="#244C3A" />
                    <rect x="42" y="4" width="18" height="18" stroke="#20241F" strokeWidth="3" />
                    <rect x="47" y="9" width="8" height="8" fill="#244C3A" />
                    <rect x="4" y="42" width="18" height="18" stroke="#20241F" strokeWidth="3" />
                    <rect x="9" y="47" width="8" height="8" fill="#244C3A" />
                    <rect x="26" y="8" width="4" height="4" fill="#20241F" />
                    <rect x="32" y="14" width="4" height="4" fill="#20241F" />
                    <rect x="26" y="26" width="12" height="12" fill="#244C3A" />
                    <rect x="8" y="28" width="6" height="4" fill="#20241F" />
                    <rect x="44" y="28" width="10" height="4" fill="#20241F" />
                    <rect x="28" y="44" width="6" height="6" fill="#20241F" />
                    <rect x="42" y="42" width="8" height="8" fill="#20241F" />
                    <rect x="52" y="52" width="8" height="8" fill="#244C3A" />
                  </svg>
                </div>
                <p className="text-[11px] font-mono text-[#686B65] break-all">
                  Encoded URL: {opaqueVerifyUrl}
                </p>
                <p className="text-[11px] text-[#686B65]">
                  Privacy Guardrail: QR payload contains only the opaque verification URL—never
                  APAAR IDs or personal information.
                </p>
              </div>
            </div>

            {/* Bottom Disclaimer */}
            <div className="px-6 py-3 bg-[#F0EFE9] border-t border-[#DEDDD5] text-xs text-[#686B65]">
              {data.disclaimer}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
