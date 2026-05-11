import { useState } from 'react'

const PAGE_SIZE = 3

function Pagination({ page, total, pageSize, onChange }) {
  const totalPages = Math.ceil(total / pageSize)
  if (totalPages <= 1) return null
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'flex-end', padding: '8px 0 4px', marginTop: 4 }}>
      <span style={{ fontSize: 12, color: '#718096', marginRight: 8 }}>
        {total} row{total !== 1 ? 's' : ''} &nbsp;·&nbsp; page {page} of {totalPages}
      </span>
      {[['‹', page - 1, page === 1], ...Array.from({ length: totalPages }, (_, i) => [i + 1, i + 1, false]), ['›', page + 1, page === totalPages]]
        .map(([label, target, disabled], idx) => (
          <button key={idx}
            onClick={() => !disabled && onChange(target)}
            disabled={disabled}
            style={{
              padding: '3px 9px', borderRadius: 4, border: '1px solid #e2e8f0',
              background: target === page ? '#3182ce' : '#fff',
              color: target === page ? '#fff' : '#4a5568',
              cursor: disabled ? 'default' : 'pointer', fontWeight: 500, fontSize: 12,
            }}
          >{label}</button>
        ))
      }
    </div>
  )
}

/** ResourcesSummary – shows a table of all collected resources with type/location/RG breakdown. */
export default function ResourcesSummary({ resources, loading }) {
  const [typePage, setTypePage] = useState(1)
  const [resPage, setResPage] = useState(1)

  const card = { background: '#fff', borderRadius: 8, padding: '16px 20px', boxShadow: '0 1px 4px rgba(0,0,0,0.08)', marginBottom: 24 }
  const thStyle = { padding: '9px 12px', background: '#edf2f7', fontWeight: 600, fontSize: 12, textAlign: 'left', borderBottom: '1px solid #e2e8f0' }
  const tdStyle = { padding: '9px 12px', fontSize: 13, borderBottom: '1px solid #f0f4f8' }

  // Compute type breakdown
  const byType = {}
  for (const r of resources) {
    const t = r.type || 'Unknown'
    if (!byType[t]) byType[t] = { count: 0, locations: new Set(), rgs: new Set() }
    byType[t].count++
    if (r.location) byType[t].locations.add(r.location)
    if (r.resource_group) byType[t].rgs.add(r.resource_group)
  }
  const allRows = Object.entries(byType).sort((a, b) => b[1].count - a[1].count)
  const typeTotal = allRows.length
  const typeTotalPages = Math.ceil(typeTotal / PAGE_SIZE)
  const safeTypePage = Math.min(typePage, Math.max(1, typeTotalPages))
  const typeSlice = allRows.slice((safeTypePage - 1) * PAGE_SIZE, safeTypePage * PAGE_SIZE)

  const resTotal = resources.length
  const resTotalPages = Math.ceil(resTotal / PAGE_SIZE)
  const safeResPage = Math.min(resPage, Math.max(1, resTotalPages))
  const resSlice = resources.slice((safeResPage - 1) * PAGE_SIZE, safeResPage * PAGE_SIZE)

  return (
    <div style={card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <span style={{ fontSize: 13, color: '#718096' }}>
          {resources.length} resource{resources.length !== 1 ? 's' : ''} collected
        </span>
        {loading && <span style={{ fontSize: 12, color: '#718096' }}>Loading…</span>}
      </div>

      {!loading && resources.length === 0 && (
        <p style={{ color: '#a0aec0', fontSize: 13, margin: 0 }}>
          No resources found. Run extraction first.
        </p>
      )}

      {resources.length > 0 && (
        <>
          {/* Per-type breakdown with pagination */}
          <div style={{ overflowX: 'auto', marginBottom: 4 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Resource Type', 'Count', 'Locations', 'Resource Groups'].map(h => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {typeSlice.map(([type, info]) => (
                  <tr key={type}>
                    <td style={tdStyle}>
                      <span style={{ fontFamily: 'monospace', fontSize: 12 }}>
                        {type.split('/').pop()}
                      </span>
                      <div style={{ fontSize: 11, color: '#a0aec0' }}>{type}</div>
                    </td>
                    <td style={{ ...tdStyle, fontWeight: 700, textAlign: 'center' }}>{info.count}</td>
                    <td style={{ ...tdStyle, fontSize: 12, color: '#4a5568' }}>
                      {[...info.locations].join(', ') || '—'}
                    </td>
                    <td style={{ ...tdStyle, fontSize: 12, color: '#4a5568' }}>
                      {[...info.rgs].join(', ') || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={safeTypePage} total={typeTotal} pageSize={PAGE_SIZE} onChange={setTypePage} />

          {/* Individual resource list with pagination */}
          <details style={{ marginTop: 16 }}>
            <summary style={{ fontSize: 13, color: '#3182ce', cursor: 'pointer', marginBottom: 8 }}>
              Show all {resources.length} resources
            </summary>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Name', 'Type', 'Resource Group', 'Location', 'SKU'].map(h => (
                      <th key={h} style={thStyle}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {resSlice.map((r) => (
                    <tr key={r.id || r.resource_id}>
                      <td style={{ ...tdStyle, fontWeight: 500 }}>{r.name || '—'}</td>
                      <td style={{ ...tdStyle, fontSize: 11, color: '#718096' }}>
                        {(r.type || '').split('/').pop()}
                      </td>
                      <td style={tdStyle}>{r.resource_group || '—'}</td>
                      <td style={tdStyle}>{r.location || '—'}</td>
                      <td style={{ ...tdStyle, fontSize: 11, color: '#718096' }}>{r.sku || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={safeResPage} total={resTotal} pageSize={PAGE_SIZE} onChange={setResPage} />
          </details>
        </>
      )}
    </div>
  )
}
