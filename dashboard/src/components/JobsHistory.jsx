/** JobsHistory – displays all job runs with start time, duration, status, and counts. */
export default function JobsHistory({ jobs }) {
  const card = { background: '#fff', borderRadius: 8, boxShadow: '0 1px 4px rgba(0,0,0,0.08)', overflowX: 'auto' }
  const thStyle = { padding: '9px 12px', background: '#edf2f7', fontWeight: 600, fontSize: 12, textAlign: 'left', borderBottom: '1px solid #e2e8f0', whiteSpace: 'nowrap' }
  const tdStyle = { padding: '9px 12px', fontSize: 13, borderBottom: '1px solid #f0f4f8', whiteSpace: 'nowrap' }

  const statusColor = {
    completed: { bg: '#c6f6d5', text: '#276749' },
    failed:    { bg: '#fed7d7', text: '#9b2c2c' },
    running:   { bg: '#bee3f8', text: '#2a69ac' },
    pending:   { bg: '#fefcbf', text: '#975a16' },
  }

  const fmt = (iso) => {
    if (!iso) return '—'
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  }

  const duration = (start, end) => {
    if (!start) return '—'
    const s = new Date(end || Date.now()) - new Date(start)
    if (s < 0) return '—'
    const sec = Math.floor(s / 1000)
    if (sec < 60) return `${sec}s`
    const min = Math.floor(sec / 60)
    return `${min}m ${sec % 60}s`
  }

  if (!jobs?.length) {
    return (
      <div style={{ ...card, padding: '20px' }}>
        <p style={{ color: '#a0aec0', fontSize: 13, margin: 0 }}>No job runs yet.</p>
      </div>
    )
  }

  return (
    <div style={card}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {['Run ID', 'Started At', 'Completed At', 'Duration', 'Status', 'Resources', 'Costs', 'Findings', 'Error'].map(h => (
              <th key={h} style={thStyle}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {jobs.map((j) => {
            const sc = statusColor[j.status] || { bg: '#e2e8f0', text: '#4a5568' }
            return (
              <tr key={j.id} style={{ background: '#fff' }}>
                <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: 11, color: '#718096' }}>
                  {j.id?.slice(0, 8)}…
                </td>
                <td style={tdStyle}>{fmt(j.started_at)}</td>
                <td style={tdStyle}>{fmt(j.completed_at)}</td>
                <td style={{ ...tdStyle, color: '#4a5568' }}>
                  {duration(j.started_at, j.completed_at)}
                </td>
                <td style={tdStyle}>
                  <span style={{
                    background: sc.bg, color: sc.text,
                    padding: '2px 9px', borderRadius: 4,
                    fontWeight: 600, fontSize: 11,
                  }}>
                    {j.status}
                  </span>
                </td>
                <td style={{ ...tdStyle, textAlign: 'center', fontWeight: j.resources_count > 0 ? 600 : 400 }}>
                  {j.resources_count ?? 0}
                </td>
                <td style={{ ...tdStyle, textAlign: 'center' }}>
                  {j.cost_records_count ?? 0}
                </td>
                <td style={{ ...tdStyle, textAlign: 'center', color: j.findings_count > 0 ? '#e53e3e' : 'inherit', fontWeight: j.findings_count > 0 ? 600 : 400 }}>
                  {j.findings_count ?? 0}
                </td>
                <td style={{ ...tdStyle, fontSize: 11, color: '#e53e3e', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}
                  title={j.error_message || ''}>
                  {j.error_message ? j.error_message.slice(0, 60) + (j.error_message.length > 60 ? '…' : '') : ''}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
