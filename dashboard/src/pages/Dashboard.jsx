import { useEffect, useState, useCallback } from 'react'
import CostSummary from '../components/CostSummary'
import ResourceTable from '../components/ResourceTable'
import ResourcesSummary from '../components/ResourcesSummary'
import JobsHistory from '../components/JobsHistory'
import ScriptDownload from '../components/ScriptDownload'

const API = ''

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [findings, setFindings] = useState([])
  const [resources, setResources] = useState([])
  const [jobs, setJobs] = useState([])
  const [identity, setIdentity] = useState(null)
  const [loadingFindings, setLoadingFindings] = useState(false)
  const [loadingResources, setLoadingResources] = useState(false)
  const [jobStatus, setJobStatus] = useState(null)
  const [triggering, setTriggering] = useState(false)
  const [polling, setPolling] = useState(false)

  const fetchSummary = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/v1/dashboard/summary`)
      if (res.ok) setSummary(await res.json())
    } catch (_) {}
  }, [])

  const fetchFindings = useCallback(async () => {
    setLoadingFindings(true)
    try {
      const res = await fetch(`${API}/api/v1/findings/`)
      if (res.ok) { const d = await res.json(); setFindings(d.items || []) }
    } catch (_) {}
    setLoadingFindings(false)
  }, [])

  const fetchResources = useCallback(async () => {
    setLoadingResources(true)
    try {
      const res = await fetch(`${API}/api/v1/resources/`)
      if (res.ok) { const d = await res.json(); setResources(d.items || []) }
    } catch (_) {}
    setLoadingResources(false)
  }, [])

  const fetchJobs = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/v1/jobs`)
      if (res.ok) setJobs(await res.json())
    } catch (_) {}
  }, [])

  const fetchIdentity = useCallback(async () => {
    try {
      const res = await fetch('/.auth/me')
      if (!res.ok) return
      const data = await res.json()
      // /.auth/me returns an array of identity providers
      const claims = data?.[0]?.user_claims || []
      const name =
        claims.find(c => c.typ === 'name')?.val ||
        claims.find(c => c.typ === 'preferred_username')?.val ||
        claims.find(c => c.typ === 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name')?.val ||
        data?.[0]?.user_id ||
        null
      if (name) setIdentity({ display_name: name })
    } catch (_) {}
  }, [])

  const refreshAll = useCallback(() => {
    fetchSummary(); fetchFindings(); fetchResources(); fetchJobs()
  }, [fetchSummary, fetchFindings, fetchResources, fetchJobs])

  useEffect(() => { refreshAll(); fetchIdentity() }, [refreshAll, fetchIdentity])

  const triggerExtraction = async () => {
    setTriggering(true)
    setJobStatus({ status: 'pending' })
    try {
      const res = await fetch(`${API}/api/v1/jobs/extract-all`, { method: 'POST' })
      if (!res.ok) throw new Error('Failed to trigger job')
      const job = await res.json()
      setJobStatus(job)
      fetchJobs()
      pollJob(job.id)
    } catch (e) {
      setJobStatus({ status: 'error', error: e.message })
    }
    setTriggering(false)
  }

  const pollJob = (jobId) => {
    setPolling(true)
    const iv = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/v1/jobs/${jobId}`)
        if (!res.ok) return
        const job = await res.json()
        setJobStatus(job)
        fetchJobs()
        if (job.status === 'completed' || job.status === 'failed') {
          clearInterval(iv)
          setPolling(false)
          refreshAll()
        }
      } catch (_) {}
    }, 5000)
  }

  const statusColor = {
    completed: '#38a169', failed: '#e53e3e', running: '#3182ce', pending: '#d69e2e',
  }

  const sectionHead = { fontSize: 13, fontWeight: 700, marginBottom: 6, marginTop: 20, color: '#2d3748', textTransform: 'uppercase', letterSpacing: '0.05em' }

  return (
    <div style={{ maxWidth: 1280, margin: '0 auto', padding: '14px 16px', fontFamily: 'system-ui, sans-serif', background: '#f7fafc', minHeight: '100vh' }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0, lineHeight: 1.2 }}>☁ Cloud Cost Optimizer</h1>
          <p style={{ fontSize: 12, color: '#718096', marginTop: 2, marginBottom: 0 }}>
            Azure FinOps — Orphaned &amp; Idle Resource Detection
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Identity chip */}
          {identity && (
            <span style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '4px 10px', borderRadius: 20, background: '#f0fff4',
              border: '1px solid #9ae6b4', fontSize: 12, color: '#276749',
            }}>
              <span style={{ fontSize: 13 }}>👤</span>
              <span style={{ fontWeight: 600 }}>{identity.display_name}</span>
            </span>
          )}
          {jobStatus && (
            <span style={{
              padding: '3px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600,
              background: (statusColor[jobStatus.status] || '#718096') + '20',
              color: statusColor[jobStatus.status] || '#718096',
            }}>
              {polling ? '⟳ ' : ''}{jobStatus.status}
            </span>
          )}
          <button
            onClick={triggerExtraction}
            disabled={triggering || polling}
            style={{
              padding: '7px 16px',
              background: triggering || polling ? '#a0aec0' : '#3182ce',
              color: '#fff', border: 'none', borderRadius: 6,
              cursor: triggering || polling ? 'default' : 'pointer',
              fontWeight: 600, fontSize: 13,
            }}
          >
            {triggering ? 'Starting…' : polling ? '⟳ Running…' : '▶ Run Extraction'}
          </button>
          <button
            onClick={refreshAll}
            title="Refresh all data"
            style={{
              padding: '7px 12px', background: '#fff',
              border: '1px solid #e2e8f0', borderRadius: 6,
              cursor: 'pointer', fontSize: 15,
            }}
          >↻</button>
        </div>
      </div>

      {/* ── KPI Summary Cards ── */}
      <CostSummary summary={summary} />

      {/* ── Findings Table ── */}
      <p style={sectionHead}>Findings — Orphaned &amp; Idle Resources</p>
      <ResourceTable findings={findings} loading={loadingFindings} />

      {/* ── Remediation Scripts ── */}
      <p style={sectionHead}>Remediation Scripts</p>
      <div style={{ background: '#fff', borderRadius: 8, boxShadow: '0 1px 4px rgba(0,0,0,0.08)', padding: '12px 16px' }}>
        {findings.length === 0 ? (
          <p style={{ margin: 0, fontSize: 13, color: '#a0aec0' }}>
            No findings yet — run extraction first to enable script generation.
          </p>
        ) : (
          <ScriptDownload runId={summary?.last_run_id} scriptReady={summary?.script_ready} hasFindings={findings.length > 0} />
        )}
      </div>

      {/* ── Resources Summary Table ── */}
      <p style={sectionHead}>Resources Collected</p>
      <ResourcesSummary resources={resources} loading={loadingResources} />

      {/* ── Job Run History ── */}
      <p style={sectionHead}>Job Run History</p>
      <JobsHistory jobs={jobs} />

      {/* ── Footer ── */}
      <p style={{ textAlign: 'center', marginTop: 20, fontSize: 11, color: '#a0aec0' }}>
        Cloud Cost Optimizer &amp; Remediation Engine &nbsp;|&nbsp; Last updated:{' '}
        {summary?.last_run_at ? new Date(summary.last_run_at).toLocaleString() : '—'}
      </p>
    </div>
  )
}
