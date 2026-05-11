import { useState } from 'react'

/** Generate scripts and download ZIP. */
export default function ScriptDownload({ runId, scriptReady: initialReady, hasFindings = false }) {
  const [generating, setGenerating] = useState(false)
  const [ready, setReady] = useState(initialReady)
  const [error, setError] = useState(null)

  const btnStyle = (color) => ({
    padding: '10px 20px', background: color, color: '#fff',
    border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 14,
  })

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const res = await fetch('/api/v1/scripts/generate', { method: 'POST' })
      if (!res.ok) throw new Error(await res.text())
      setReady(true)
    } catch (e) {
      setError(e.message)
    } finally {
      setGenerating(false)
    }
  }

  const handleDownload = () => {
    window.location.href = '/api/v1/scripts/download-all'
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
      {!ready && (
        <button style={btnStyle(hasFindings ? '#3182ce' : '#a0aec0')} onClick={handleGenerate} disabled={generating || !hasFindings}>
          {generating ? 'Generating…' : '⚙ Generate Remediation Scripts'}
        </button>
      )}
      {ready && (
        <button style={btnStyle('#38a169')} onClick={handleDownload}>
          ⬇ Download Scripts (.zip)
        </button>
      )}
      {ready && (
        <button style={{ ...btnStyle('#718096'), background: '#edf2f7', color: '#4a5568' }}
          onClick={handleGenerate} disabled={generating}>
          ↺ Regenerate
        </button>
      )}
      {error && <span style={{ color: '#e53e3e', fontSize: 13 }}>{error}</span>}
    </div>
  )
}
