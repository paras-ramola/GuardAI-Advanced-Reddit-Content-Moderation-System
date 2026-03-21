import { useState } from 'react'
import { api } from '../api'

function highlightText(text, toxicWords) {
  if (!toxicWords?.length) return text
  const escaped = toxicWords.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const regex   = new RegExp(`\\b(${escaped.join('|')})\\b`, 'gi')
  const parts   = text.split(regex)
  return parts.map((part, i) =>
    regex.test(part) ? <mark key={i} className="toxic-word">{part}</mark> : part
  )
}

export default function Predict() {
  const [text,    setText]    = useState('')
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')
  const [result,  setResult]  = useState(null)

  const charLimit = 500

  async function handlePredict() {
    const t = text.trim()
    if (!t) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await api.predict(t)
      setResult(res.data)
    } catch(e) {
      setError(e.response?.data?.error || 'Failed to get prediction. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  const confPct = result ? (result.confidence * 100).toFixed(1) : 0

  return (
    <div>
      <div className="page-title">Quick Predict</div>
      <div className="page-subtitle">Classify any text for hate speech instantly</div>

      <div className="card" style={{marginBottom: 0}}>
        <textarea
          id="predict-textarea"
          className="textarea-field"
          placeholder="Paste any Reddit post, comment, or custom text…"
          value={text}
          onChange={e => setText(e.target.value.slice(0, charLimit))}
          style={{marginBottom:12}}
        />
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
          <span style={{fontSize:12, color: text.length >= charLimit ? 'var(--hate)' : 'var(--text-muted)'}}>
            {text.length}/{charLimit}
          </span>
          <div style={{display:'flex', gap:10}}>
            <button className="btn btn-ghost" onClick={() => { setText(''); setResult(null) }}>
              Clear
            </button>
            <button
              id="predict-btn"
              className="btn btn-primary"
              onClick={handlePredict}
              disabled={loading || !text.trim()}
            >
              {loading ? <><div className="spinner" /> Predicting…</> : '⚡ Predict'}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="error-banner" style={{marginTop:16}}>⚠️ {error}</div>}

      {/* ── Result hero ── */}
      {result && (
        <div className={`predict-result ${result.label}`}>
          <div className={`predict-label ${result.label}`}>
            {result.label === 'hate' ? '🔴 HATE SPEECH' : '🟢 SAFE'}
          </div>
          <div className="predict-conf">
            Confidence: <strong>{confPct}%</strong> &nbsp;|&nbsp;
            Severity: <strong>{(result.severity * 100).toFixed(1)}%</strong> &nbsp;|&nbsp;
            Model: <span style={{fontFamily:'JetBrains Mono', fontSize:13}}>{result.model_version}</span>
          </div>

          {/* Confidence bar */}
          <div className="confidence-bar-wrap" style={{maxWidth:400, margin:'0 auto 20px'}}>
            <div className="confidence-bar-fill" style={{
              width:`${result.confidence * 100}%`,
              background: result.label === 'hate'
                ? 'linear-gradient(90deg, var(--hate), var(--warn))'
                : 'linear-gradient(90deg, var(--safe), var(--accent))',
            }} />
          </div>

          {/* Highlighted text */}
          <div style={{
            background:'var(--bg-700)', padding:'14px 18px',
            borderRadius:'var(--radius-sm)', fontSize:14,
            lineHeight:1.7, textAlign:'left',
            border:'1px solid var(--border)', marginBottom:16,
          }}>
            {highlightText(result.input_text, result.toxic_words)}
          </div>

          {/* Toxic words */}
          {result.toxic_words?.length > 0 && (
            <div>
              <div style={{fontSize:12, color:'var(--text-muted)', marginBottom:8}}>
                Flagged words:
              </div>
              <div className="toxic-words-list">
                {result.toxic_words.map((w, i) => (
                  <span key={i} className="badge badge-hate">{w}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
