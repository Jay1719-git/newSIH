import React, { useState } from 'react';
import { Link, NavLink, Outlet, Navigate, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  FileSpreadsheet,
  Upload,
  GitCompare,
  BarChart3,
  Building2,
  BookOpen,
  History,
  MessageSquare,
  Settings,
  LogOut,
  Menu,
  X,
  ExternalLink,
  Box,
} from 'lucide-react';
import { WeaveLogo } from '../ui/WeaveLogo';
import { useAuth } from '../../lib/auth';
import { SYNTHETIC_DEMO_ACCOUNTS } from '../../lib/syntheticSeed';
import { isInstitutionScopedRole, type UserRole } from '../../lib/weaveEngine';

const ROUTE_META: Record<string, { title: string; subtitle: string; crumb: string }> = {
  '/app': {
    title: 'Operational Overview',
    subtitle: 'Role-scoped enrolment, batch validation, and intake governance telemetry.',
    crumb: 'Overview',
  },
  '/app/students': {
    title: 'Student Records Registry',
    subtitle: 'Protected student records with masked APAAR references and internal check status.',
    crumb: 'Student Records',
  },
  '/app/imports': {
    title: 'CSV Import Batches',
    subtitle: 'Chronological ledger of uploaded student batches and validation summaries.',
    crumb: 'Import Batches',
  },
  '/app/imports/new': {
    title: 'CSV Import Wizard',
    subtitle: 'Preflight column verification, row preview, and deterministic backend ingestion.',
    crumb: 'New CSV Import',
  },
  '/app/duplicates': {
    title: 'Duplicate & Conflict Review Queue',
    subtitle: 'Regulator review queue for cross-institution APAAR digest collisions.',
    crumb: 'Conflict Review',
  },
  '/app/intake': {
    title: 'Approved Intake Monitoring',
    subtitle: 'AICTE sanctioned program capacity versus committed student enrolment.',
    crumb: 'Intake Monitoring',
  },
  '/app/institutions': {
    title: 'Participating Institutions',
    subtitle: 'Registered technical institutions and tenant isolation boundaries.',
    crumb: 'Institutions',
  },
  '/app/programs': {
    title: 'Program & Sanctioned Intake Registry',
    subtitle: 'Approved AICTE discipline codes (STU-002) and annual seat allocations.',
    crumb: 'Programs',
  },
  '/app/audit': {
    title: 'Audit Timeline & Rulebook',
    subtitle: 'Append-only chronological audit trail with SHA-256 hash-chain verification.',
    crumb: 'Audit Timeline',
  },
  '/app/assistant': {
    title: 'Administrative Guidance Copilot (Read-Only)',
    subtitle: 'Multi-turn Gemini copilot and voice transcription (gemini-3.5-transcribe) for rules and intake.',
    crumb: 'Admin Copilot',
  },
  '/app/settings': {
    title: 'Workspace & Session Settings',
    subtitle: 'Active role profile, API mode configuration, and attestation management.',
    crumb: 'Settings',
  },
};

export const AppShell: React.FC = () => {
  const { user, apiMode, isAuthenticated, isLoading, switchRolePersona, logout } = useAuth();

  if (apiMode === 'live' && isLoading) {
    return <div role="status" className="min-h-screen p-8 text-sm text-[#686B65]">Restoring authenticated session…</div>;
  }
  if (apiMode === 'live' && !isAuthenticated) return <Navigate to="/login" replace />;
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const isBatchDetail =
    location.pathname.startsWith('/app/imports/') &&
    location.pathname !== '/app/imports/new';
  const currentMeta = isBatchDetail
    ? {
        title: `Batch Validation Results (${location.pathname.split('/').pop()})`,
        subtitle:
          'Expandable deterministic issue diagnostics, remediation guidance, and commit eligibility.',
        crumb: `Batch ${location.pathname.split('/').pop()}`,
      }
    : ROUTE_META[location.pathname] || ROUTE_META['/app'];

  const instScoped = isInstitutionScopedRole(user.role);

  const navItems = [
    { to: '/app', label: 'Overview', icon: LayoutDashboard, end: true },
    { to: '/app/topology', label: '3D Spatial Topology', icon: Box, badge: 'Live 3D' },
    { to: '/app/students', label: 'Student Records', icon: Users },
    { to: '/app/imports', label: 'Import Batches', icon: FileSpreadsheet },
    { to: '/app/imports/new', label: 'CSV Import Wizard', icon: Upload },
    {
      to: '/app/duplicates',
      label: 'Conflict Review',
      icon: GitCompare,
      badge: instScoped ? 'Restricted' : undefined,
    },
    { to: '/app/intake', label: 'Intake Monitoring', icon: BarChart3 },
    { to: '/app/institutions', label: 'Institutions', icon: Building2 },
    { to: '/app/programs', label: 'Programs & Caps', icon: BookOpen },
    { to: '/app/audit', label: 'Audit Timeline', icon: History },
    { to: '/app/assistant', label: 'Admin Copilot', icon: MessageSquare },
    { to: '/app/settings', label: 'Settings & Credentials', icon: Settings },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-[#F7F6F2] text-[#20241F]">
      {/* Persistent Synthetic / Mock Disclosure Banner */}
      <div
        role="region"
        aria-label="Synthetic data environment disclosure"
        className="bg-[#E9E7DF] border-b border-[#DEDDD5] px-4 sm:px-6 py-1.5 text-xs flex flex-wrap items-center justify-between gap-2"
      >
        <div className="flex items-center gap-2 font-mono text-[11px] font-medium text-[#20241F]">
          <span className="px-1.5 py-0.5 bg-[#244C3A] text-white rounded-xs">
            {apiMode === 'mock'
              ? 'MOCK API — NOT REAL DATA'
              : 'SYNTHETIC DATA — DEMONSTRATION ONLY'}
          </span>
          <span>
            SIH26263 · No live government APAAR/AICTE connection · Masked APAAR enforced
          </span>
        </div>

        <div className="flex items-center gap-3 text-xs">
          {apiMode === 'mock' ? (
          <Link
            to="/verify/att-2026-901"
            className="inline-flex items-center gap-1 font-mono text-[11px] text-[#244C3A] hover:underline"
          >
            <span>Public Verifier (/verify/att-2026-901)</span>
            <ExternalLink className="w-3 h-3" />
          </Link>
          ) : (
            <span className="text-[#8E6218]">Public verification is unavailable in the FastAPI backend.</span>
          )}
        </div>
      </div>

      <div className="flex-1 flex">
        {/* Desktop Left Sidebar */}
        <aside
          aria-label="Workspace Sidebar Navigation"
          className="hidden lg:flex lg:w-64 xl:w-68 flex-col bg-white border-r border-[#DEDDD5] shrink-0"
        >
          <div className="h-16 px-5 border-b border-[#DEDDD5] flex items-center justify-between">
            <Link to="/" aria-label="WEAVE Public Home">
              <WeaveLogo />
            </Link>
            <span className="font-mono text-[11px] text-[#686B65]">v0.1.0</span>
          </div>

          <div className="p-4 border-b border-[#DEDDD5] bg-[#F7F6F2]/60 space-y-2">
            <div className="text-[11px] font-mono uppercase tracking-wider text-[#686B65]">
              Authenticated Profile
            </div>
            <div className="text-xs font-semibold text-[#20241F] truncate">{user.name}</div>
            <div className="text-[11px] font-mono text-[#244C3A]">{user.role}</div>
            {user.institution_id && (
              <div className="text-[11px] font-mono text-[#686B65] truncate">
                Tenant: {user.institution_id}
              </div>
            )}
          </div>

          <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `flex items-center justify-between gap-2.5 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                      isActive
                        ? 'bg-[#244C3A] text-white'
                        : 'text-[#20241F] hover:bg-[#F0EFE9]'
                    }`
                  }
                >
                  <span className="flex items-center gap-2.5 truncate">
                    <Icon className="w-4 h-4 shrink-0" />
                    <span className="truncate">{item.label}</span>
                  </span>
                  {item.badge && (
                    <span className="font-mono text-[10px] opacity-75 shrink-0">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </nav>

          <div className="p-4 border-t border-[#DEDDD5] space-y-2">
            <button
              type="button"
              onClick={() => {
                logout();
                navigate('/login');
              }}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-[#20241F] bg-[#F7F6F2] hover:bg-[#E9E7DF] border border-[#DEDDD5] rounded-md transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Switch Account / Sign Out</span>
            </button>
          </div>
        </aside>

        {/* Main Workspace Column */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Top Bar */}
          <header className="bg-white border-b border-[#DEDDD5] px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                aria-label="Toggle workspace navigation"
                onClick={() => setMobileNavOpen((prev) => !prev)}
                className="lg:hidden p-1.5 text-[#20241F] border border-[#DEDDD5] rounded-md"
              >
                {mobileNavOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
              </button>

              {/* Breadcrumbs */}
              <nav aria-label="Breadcrumb" className="text-xs text-[#686B65] flex items-center gap-2">
                <Link to="/app" className="hover:text-[#20241F] font-medium">
                  Workspace
                </Link>
                <span aria-hidden="true">/</span>
                <span className="text-[#20241F] font-semibold">{currentMeta.crumb}</span>
              </nav>
            </div>

            {/* Role & Tenant Switcher Controls for Demonstration Inspection */}
            {apiMode === 'mock' ? <div className="flex flex-wrap items-center gap-3 text-xs">
              <div className="flex items-center gap-1.5">
                <label htmlFor="topbar-role-select" className="text-[#686B65] font-medium">
                  Role:
                </label>
                <select
                  id="topbar-role-select"
                  value={user.role}
                  onChange={(e) => switchRolePersona(e.target.value as UserRole, user.institution_id)}
                  className="px-2.5 py-1.5 text-xs font-mono bg-[#F7F6F2] border border-[#DEDDD5] rounded-md text-[#20241F] focus:outline-none focus:ring-2 focus:ring-[#244C3A]"
                >
                  {SYNTHETIC_DEMO_ACCOUNTS.map((acct) => (
                    <option key={acct.role} value={acct.role}>
                      {acct.role} ({acct.roleLabel})
                    </option>
                  ))}
                </select>
              </div>

              {instScoped && (
                <div className="flex items-center gap-1.5">
                  <label htmlFor="topbar-tenant-select" className="text-[#686B65] font-medium">
                    Institution:
                  </label>
                  <select
                    id="topbar-tenant-select"
                    value={user.institution_id || 'INST-KKR-101'}
                    onChange={(e) => switchRolePersona(user.role, e.target.value)}
                    className="px-2.5 py-1.5 text-xs font-mono bg-[#F7F6F2] border border-[#DEDDD5] rounded-md text-[#20241F] focus:outline-none focus:ring-2 focus:ring-[#244C3A]"
                  >
                    <option value="INST-KKR-101">INST-KKR-101 (NIT Kurukshetra)</option>
                    <option value="INST-DEL-202">INST-DEL-202 (IIET Delhi)</option>
                    <option value="INST-PUN-305">INST-PUN-305 (DCAE Pune)</option>
                  </select>
                </div>
              )}
            </div> : (
              <div className="text-xs text-[#686B65]">
                Authenticated API account: <span className="font-mono">{user.role}</span>
              </div>
            )}
          </header>

          {/* Mobile Drawer Navigation */}
          {mobileNavOpen && (
            <nav
              aria-label="Mobile Workspace Navigation"
              className="lg:hidden bg-white border-b border-[#DEDDD5] p-4 grid grid-cols-2 gap-2"
            >
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={() => setMobileNavOpen(false)}
                  className={({ isActive }) =>
                    `px-3 py-2 rounded-md text-xs font-medium ${
                      isActive ? 'bg-[#244C3A] text-white' : 'bg-[#F7F6F2] text-[#20241F]'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          )}

          {/* Page Header & Outlet */}
          <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-8 space-y-6">
            <div className="pb-5 border-b border-[#DEDDD5] flex flex-col sm:flex-row sm:items-end justify-between gap-4">
              <div>
                <h1 className="font-display text-2xl font-bold text-[#20241F]">
                  {currentMeta.title}
                </h1>
                <p className="mt-1 text-xs text-[#686B65]">{currentMeta.subtitle}</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Link
                  to="/app/imports/new"
                  className="px-3.5 py-2 text-xs font-medium text-white bg-[#244C3A] hover:bg-[#193B2C] rounded-md transition-colors whitespace-nowrap"
                >
                  Import CSV Batch
                </Link>
              </div>
            </div>

            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
};
