import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Search,
  ArrowUpDown,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
} from 'lucide-react';
import { useAuth } from '../../lib/auth';
import { weaveApiClient, weaveQueryKeys } from '../../lib/api-client';
import type { ApiStudentRecord } from '../../lib/api-client';

export const StudentsPage: React.FC = () => {
  const { user } = useAuth();
  const [search, setSearch] = useState('');
  const [programFilter, setProgramFilter] = useState('ALL');
  const [yearFilter, setYearFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [sortField, setSortField] = useState<'full_name' | 'student_ref' | 'enrollment_year'>(
    'student_ref'
  );
  const [sortAsc, setSortAsc] = useState(true);
  const [page, setPage] = useState(1);
  const pageSize = 6;

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: weaveQueryKeys.validationResults(user.role, user.institution_id),
    queryFn: () => weaveApiClient.getValidationResults(user.role, user.institution_id),
  });

  const students = data?.students || [];
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const filteredAndSorted = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = students.filter((s) => {
      if (programFilter !== 'ALL' && s.program_code !== programFilter) return false;
      if (yearFilter !== 'ALL' && String(s.enrollment_year) !== yearFilter) return false;
      if (statusFilter !== 'ALL' && s.status !== statusFilter) return false;
      if (
        q &&
        !s.full_name.toLowerCase().includes(q) &&
        !s.student_ref.toLowerCase().includes(q) &&
        !s.apaar_masked.toLowerCase().includes(q)
      ) {
        return false;
      }
      return true;
    });

    return [...filtered].sort((a, b) => {
      const valA = a[sortField];
      const valB = b[sortField];
      const cmp = String(valA).localeCompare(String(valB), undefined, { numeric: true });
      return sortAsc ? cmp : -cmp;
    });
  }, [students, search, programFilter, yearFilter, statusFilter, sortField, sortAsc]);

  const totalPages = Math.max(1, Math.ceil(filteredAndSorted.length / pageSize));
  const paginated = filteredAndSorted.slice((page - 1) * pageSize, page * pageSize);
  const selectedStudent: ApiStudentRecord | null =
    filteredAndSorted.find((s) => s.id === selectedId) || paginated[0] || null;

  const toggleSort = (field: 'full_name' | 'student_ref' | 'enrollment_year') => {
    if (sortField === field) {
      setSortAsc((prev) => !prev);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  if (isLoading) {
    return (
      <div role="status" className="bg-white border border-[#DEDDD5] rounded-md p-6 space-y-3 animate-pulse">
        <div className="h-8 bg-[#F0EFE9] rounded-sm" />
        <div className="h-48 bg-[#F7F6F2] rounded-sm" />
      </div>
    );
  }

  if (isError) {
    return (
      <div role="alert" className="bg-white border border-[#99322B] rounded-md p-6 flex items-center justify-between">
        <span className="text-xs text-[#99322B]">Failed to load student records registry.</span>
        <button
          type="button"
          onClick={() => refetch()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[#F7F6F2] border border-[#DEDDD5] rounded-md"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry</span>
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Privacy Notice */}
      <div className="p-3.5 bg-[#F0EFE9] border border-[#DEDDD5] rounded-md text-xs text-[#686B65] flex flex-wrap items-center justify-between gap-2">
        <span>
          Privacy Policy: APAAR identifiers are permanently masked (`****-****-XXXX`) with no reveal
          control. Successful format validation indicates internal platform checks only—not live
          government identity proof.
        </span>
        <span className="font-mono text-[#20241F]">Synthetic Records</span>
      </div>

      {/* Filters Toolbar */}
      <div className="bg-white border border-[#DEDDD5] rounded-md p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        <div className="lg:col-span-2 relative">
          <Search className="w-3.5 h-3.5 text-[#686B65] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="search"
            aria-label="Search by student name, ref, or masked APAAR"
            placeholder="Search name, ref, or ****-4756..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-[#F7F6F2] border border-[#DEDDD5] rounded-md focus:outline-none focus:ring-2 focus:ring-[#244C3A]"
          />
        </div>

        <select
          aria-label="Filter by program code"
          value={programFilter}
          onChange={(e) => {
            setProgramFilter(e.target.value);
            setPage(1);
          }}
          className="px-3 py-1.5 text-xs font-mono bg-[#F7F6F2] border border-[#DEDDD5] rounded-md"
        >
          <option value="ALL">All Programs</option>
          <option value="BTECH-CSE">BTECH-CSE</option>
          <option value="BTECH-ECE">BTECH-ECE</option>
          <option value="BTECH-ME">BTECH-ME</option>
          <option value="MTECH-AI">MTECH-AI</option>
          <option value="MBA-CORE">MBA-CORE</option>
          <option value="MCA-GEN">MCA-GEN</option>
        </select>

        <select
          aria-label="Filter by academic year"
          value={yearFilter}
          onChange={(e) => {
            setYearFilter(e.target.value);
            setPage(1);
          }}
          className="px-3 py-1.5 text-xs font-mono bg-[#F7F6F2] border border-[#DEDDD5] rounded-md"
        >
          <option value="ALL">All Academic Years</option>
          <option value="2026">AY 2026–27</option>
          <option value="2025">AY 2025–26</option>
        </select>

        <select
          aria-label="Filter by verification status"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="px-3 py-1.5 text-xs bg-[#F7F6F2] border border-[#DEDDD5] rounded-md"
        >
          <option value="ALL">All Verification States</option>
          <option value="VERIFIED">Verified by Platform Checks</option>
          <option value="FLAGGED_CONFLICT">Awaiting Conflict Review</option>
          <option value="PENDING_REVIEW">Awaiting Consent</option>
          <option value="VALIDATION_FAILED">Invalid / Incomplete Record</option>
        </select>
      </div>

      {/* Table + Student Detail Split */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-8 bg-white border border-[#DEDDD5] rounded-md overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#DEDDD5] bg-[#F0EFE9] text-xs font-medium text-[#686B65]">
                  <th className="py-2.5 px-4">
                    <button
                      type="button"
                      onClick={() => toggleSort('student_ref')}
                      className="inline-flex items-center gap-1 hover:text-[#20241F]"
                    >
                      <span>Student Ref</span>
                      <ArrowUpDown className="w-3 h-3" />
                    </button>
                  </th>
                  <th className="py-2.5 px-4">
                    <button
                      type="button"
                      onClick={() => toggleSort('full_name')}
                      className="inline-flex items-center gap-1 hover:text-[#20241F]"
                    >
                      <span>Student Name</span>
                      <ArrowUpDown className="w-3 h-3" />
                    </button>
                  </th>
                  <th className="py-2.5 px-4">Masked APAAR</th>
                  <th className="py-2.5 px-4">Program</th>
                  <th className="py-2.5 px-4">
                    <button
                      type="button"
                      onClick={() => toggleSort('enrollment_year')}
                      className="inline-flex items-center gap-1 hover:text-[#20241F]"
                    >
                      <span>Year</span>
                      <ArrowUpDown className="w-3 h-3" />
                    </button>
                  </th>
                  <th className="py-2.5 px-4 text-right">Internal Check Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#DEDDD5] text-xs">
                {paginated.map((s) => {
                  const active = selectedStudent?.id === s.id;
                  return (
                    <tr
                      key={s.id}
                      onClick={() => setSelectedId(s.id)}
                      className={`cursor-pointer transition-colors ${
                        active ? 'bg-[#F0EFE9]' : 'hover:bg-[#F7F6F2]'
                      }`}
                    >
                      <td className="py-3 px-4 font-mono font-medium text-[#20241F] tabular-nums">
                        {s.student_ref}
                      </td>
                      <td className="py-3 px-4 font-medium text-[#20241F]">{s.full_name}</td>
                      <td className="py-3 px-4 font-mono text-[#686B65] tabular-nums">
                        {s.apaar_masked}
                      </td>
                      <td className="py-3 px-4 font-mono text-[#20241F] tabular-nums">
                        {s.program_code}
                      </td>
                      <td className="py-3 px-4 font-mono text-[#686B65] tabular-nums">
                        {s.enrollment_year}
                      </td>
                      <td className="py-3 px-4 text-right font-mono">
                        {s.status === 'VERIFIED' && (
                          <span className="inline-flex items-center gap-1 text-[#1E563B] font-medium">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Platform Verified</span>
                          </span>
                        )}
                        {(s.status === 'FLAGGED_CONFLICT' || s.status === 'PENDING_REVIEW') && (
                          <span className="inline-flex items-center gap-1 text-[#8E6218] font-medium">
                            <AlertTriangle className="w-3.5 h-3.5" />
                            <span>Awaiting Review</span>
                          </span>
                        )}
                        {s.status === 'VALIDATION_FAILED' && (
                          <span className="inline-flex items-center gap-1 text-[#99322B] font-medium">
                            <XCircle className="w-3.5 h-3.5" />
                            <span>Invalid Record</span>
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
                {paginated.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-10 text-center text-xs text-[#686B65]">
                      <div>No student records match the current filters.</div>
                      <button
                        type="button"
                        onClick={() => {
                          setSearch('');
                          setProgramFilter('ALL');
                          setYearFilter('ALL');
                          setStatusFilter('ALL');
                        }}
                        className="mt-2 px-3 py-1.5 text-xs font-medium text-[#244C3A] underline"
                      >
                        Reset all filters
                      </button>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer */}
          <div className="px-4 py-3 bg-[#F7F6F2] border-t border-[#DEDDD5] flex items-center justify-between text-xs">
            <span className="font-mono text-[#686B65] tabular-nums">
              Showing {paginated.length} of {filteredAndSorted.length} record(s)
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-2.5 py-1 bg-white border border-[#DEDDD5] rounded-sm disabled:opacity-40"
              >
                Previous
              </button>
              <span className="font-mono tabular-nums">
                Page {page} / {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="px-2.5 py-1 bg-white border border-[#DEDDD5] rounded-sm disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </div>

        {/* Selected Student Detail Panel */}
        <div className="lg:col-span-4 bg-white border border-[#DEDDD5] rounded-md p-5 space-y-4">
          {selectedStudent ? (
            <>
              <div className="pb-3 border-b border-[#DEDDD5]">
                <div className="font-mono text-[11px] text-[#686B65]">
                  Synthetic Demonstration Record · {selectedStudent.id}
                </div>
                <h2 className="mt-1 font-display text-lg font-semibold text-[#20241F]">
                  {selectedStudent.full_name}
                </h2>
                <div className="mt-1 text-xs font-mono text-[#686B65] tabular-nums">
                  Ref: {selectedStudent.student_ref} · APAAR: {selectedStudent.apaar_masked}
                </div>
              </div>

              {/* Explicit Verification Distinction */}
              <div className="p-3 bg-[#F7F6F2] border border-[#DEDDD5] rounded-sm text-xs space-y-1">
                <div className="font-semibold text-[#20241F]">
                  Verification Classification:
                </div>
                {selectedStudent.status === 'VERIFIED' && (
                  <p className="text-[#1E563B]">
                    Verified by this platform’s internal deterministic checks (Ruleset 2026.10.v1).
                    Not an official government APAAR identity verification.
                  </p>
                )}
                {(selectedStudent.status === 'FLAGGED_CONFLICT' ||
                  selectedStudent.status === 'PENDING_REVIEW') && (
                  <p className="text-[#8E6218]">
                    Awaiting human review (duplicate candidate or pending student consent).
                  </p>
                )}
                {selectedStudent.status === 'VALIDATION_FAILED' && (
                  <p className="text-[#99322B]">
                    Invalid or incomplete record. Cannot be committed until rule failures are
                    remediated.
                  </p>
                )}
              </div>

              <dl className="space-y-2 text-xs font-mono tabular-nums">
                <div className="flex justify-between py-1 border-b border-[#DEDDD5]">
                  <dt className="text-[#686B65]">Institution</dt>
                  <dd className="text-[#20241F]">{selectedStudent.institution_id}</dd>
                </div>
                <div className="flex justify-between py-1 border-b border-[#DEDDD5]">
                  <dt className="text-[#686B65]">Program &amp; Year</dt>
                  <dd className="text-[#20241F]">
                    {selectedStudent.program_code} ({selectedStudent.enrollment_year})
                  </dd>
                </div>
                <div className="flex justify-between py-1 border-b border-[#DEDDD5]">
                  <dt className="text-[#686B65]">Date of Birth</dt>
                  <dd className="text-[#20241F]">{selectedStudent.dob}</dd>
                </div>
                <div className="flex justify-between py-1 border-b border-[#DEDDD5]">
                  <dt className="text-[#686B65]">Consent Status</dt>
                  <dd className="text-[#20241F]">
                    {selectedStudent.consent_granted ? 'Granted' : 'Not Recorded'}
                  </dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt className="text-[#686B65]">Source Batch</dt>
                  <dd>
                    <Link
                      to={`/app/imports/${selectedStudent.batch_id}`}
                      className="text-[#244C3A] underline"
                    >
                      {selectedStudent.batch_id}
                    </Link>
                  </dd>
                </div>
              </dl>
            </>
          ) : (
            <p className="text-xs text-[#686B65]">Select a student row to inspect details.</p>
          )}
        </div>
      </div>
    </div>
  );
};
