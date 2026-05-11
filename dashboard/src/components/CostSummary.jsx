/** Displays total waste cost and per-type breakdown. */
export default function CostSummary({ summary }) {
  if (!summary) return null
  const fmt = (n) => `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2 })}`

  const cardStyle = {
    background: '#fff', borderRadius: 8, padding: '16px 24px',
    boxShadow: '0 1px 4px rgba(0,0,0,0.1)', minWidth: 180,
  }

  return (
    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 24 }}>
      <div style={cardStyle}>
        <div style={{ fontSize: 12, color: '#718096', marginBottom: 4 }}>Total Resources</div>
        <div style={{ fontSize: 28, fontWeight: 700 }}>{summary.total_resources}</div>
      </div>
      <div style={cardStyle}>
        <div style={{ fontSize: 12, color: '#718096', marginBottom: 4 }}>Findings</div>
        <div style={{ fontSize: 28, fontWeight: 700, color: '#e53e3e' }}>{summary.total_findings}</div>
      </div>
      <div style={cardStyle}>
        <div style={{ fontSize: 12, color: '#718096', marginBottom: 4 }}>Est. Monthly Waste</div>
        <div style={{ fontSize: 28, fontWeight: 700, color: '#dd6b20' }}>{fmt(summary.total_waste_usd)}</div>
      </div>
      <div style={cardStyle}>
        <div style={{ fontSize: 12, color: '#718096', marginBottom: 4 }}>Last Run Status</div>
        <div style={{ fontSize: 20, fontWeight: 600, color: summary.last_run_status === 'completed' ? '#38a169' : '#718096' }}>
          {summary.last_run_status ?? '—'}
        </div>
      </div>

      {summary.findings_by_type?.length > 0 && (
        <div style={{ ...cardStyle, flex: '1 1 300px' }}>
          <div style={{ fontSize: 12, color: '#718096', marginBottom: 8 }}>Waste by Type</div>
          {summary.findings_by_type.map((t) => (
            <div key={t.finding_type} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 13 }}>
              <span>{t.finding_type.replace(/_/g, ' ')}</span>
              <span style={{ fontWeight: 600 }}>{t.count} &nbsp;|&nbsp; {fmt(t.total_waste_usd)}/mo</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
