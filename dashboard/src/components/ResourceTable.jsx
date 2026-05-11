import { useState } from 'react'

const PAGE_SIZE = 3

function Pagination({ page, total, pageSize, onChange }) {
  const totalPages = Math.ceil(total / pageSize)
  if (totalPages <= 1) return null
  const btn = (label, target, disabled) => (
    <button
      key={label}
      onClick={() => !disabled && onChange(target)}
      disabled={disabled}
      style={{
        padding: '4px 10px', margin: '0 2px', borderRadius: 4, border: '1px solid #e2e8f0',
        background: target === page ? '#3182ce' : '#fff',
        color: target === page ? '#fff' : '#4a5568',
        cursor: disabled ? 'default' : 'pointer', fontWeight: 500, fontSize: 12,
      }}
    >{label}</button>
  )
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'flex-end', padding: '10px 12px', borderTop: '1px solid #f0f4f8' }}>
      <span style={{ fontSize: 12, color: '#718096', marginRight: 8 }}>
        {total} result{total !== 1 ? 's' : ''} &nbsp;·&nbsp; page {page} of {totalPages}
      </span>
      {btn('‹', page - 1, page === 1)}
      {Array.from({ length: totalPages }, (_, i) => btn(i + 1, i + 1, false))}
      {btn('›', page + 1, page === totalPages)}
    </div>
  )
}

/** Displays findings as a table with client-side pagination (3 rows per page). */
export default function ResourceTable({ findings, loading }) {
  const [page, setPage] = useState(1)

  if (loading) return <p style={{ color: '#718096' }}>Loading findings…</p>
  if (!findings?.length) return <p style={{ color: '#718096' }}>No findings for the latest run.</p>

  const severityColor = { high: '#e53e3e', medium: '#dd6b20', low: '#d69e2e' }
  const fmt = (n) => `$${Number(n).toFixed(2)}`

  const totalPages = Math.ceil(findings.length / PAGE_SIZE)
  const safePage = Math.min(page, totalPages)
  const slice = findings.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)

  const thStyle = {
    padding: '10px 12px', background: '#edf2f7', fontWeight: 600,
    fontSize: 12, textAlign: 'left', borderBottom: '1px solid #e2e8f0',
  }
  const tdStyle = { padding: '10px 12px', fontSize: 13, borderBottom: '1px solid #f0f4f8' }

  return (
    <div style={{ background: '#fff', borderRadius: 8, boxShadow: '0 1px 4px rgba(0,0,0,0.1)' }}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Resource', 'Type', 'Resource Group', 'Finding', 'Severity', 'Est. Monthly Cost', 'Status'].map(h => (
                <th key={h} style={thStyle}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {slice.map((f) => (
              <tr key={f.id} style={{ background: '#fff' }}>
                <td style={tdStyle}>{f.resource_name}</td>
                <td style={{ ...tdStyle, fontSize: 11, color: '#718096' }}>{f.resource_type.split('/').pop()}</td>
                <td style={tdStyle}>{f.resource_group}</td>
                <td style={tdStyle}>{f.finding_type.replace(/_/g, ' ')}</td>
                <td style={tdStyle}>
                  <span style={{
                    background: severityColor[f.severity] + '20',
                    color: severityColor[f.severity],
                    padding: '2px 8px', borderRadius: 4, fontWeight: 600, fontSize: 11,
                  }}>
                    {f.severity}
                  </span>
                </td>
                <td style={{ ...tdStyle, fontWeight: 600 }}>{fmt(f.estimated_monthly_cost_usd)}</td>
                <td style={tdStyle}>
                  <span style={{
                    background: f.tag_status === 'tagged' ? '#c6f6d5' : '#fed7d7',
                    color: f.tag_status === 'tagged' ? '#276749' : '#9b2c2c',
                    padding: '2px 8px', borderRadius: 4, fontSize: 11,
                  }}>
                    {f.tag_status === 'tagged' ? 'Tagged for deletion' : 'Inactive / Waste'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={safePage} total={findings.length} pageSize={PAGE_SIZE} onChange={setPage} />
    </div>
  )
}
