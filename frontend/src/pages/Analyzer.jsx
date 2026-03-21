import { useState, useEffect } from 'react'
import { api } from '../api'

// Extend api client with subreddits endpoint
const fetchSubreddits = () =>
  fetch('/api/subreddits?limit=200').then(r => r.json()).catch(() => ({ subreddits: [] }))

function highlightText(text, toxicWords) {
  if (!toxicWords?.length) return text
  const escaped = toxicWords.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const regex   = new RegExp(`\\b(${escaped.join('|')})\\b`, 'gi')
  const parts   = text.split(regex)
  return parts.map((part, i) =>
    regex.test(part)
      ? <mark key={i} className="toxic-word">{part}</mark>
      : part
  )
}

function ResultItem({ item }) {
  const p = item.prediction
  const [feedbackState, setFeedbackState] = useState(null)

  async function handleFeedback(correction) {
    if (!p.id || feedbackState) return
    setFeedbackState('loading')
    try {
      const res = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prediction_id: p.id, correction })
      })
      if (!res.ok) throw new Error('Failed to record feedback')
      setFeedbackState('success')
    } catch (e) {
      console.error(e)
      setFeedbackState('error')
    }
  }

  return (
    <div className={`result-item ${p.label}`}>
      <div className="result-text">{highlightText(item.text, p.toxic_words)}</div>
      <div className="result-meta" style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start', flexWrap:'wrap', gap:8}}>
        <div style={{display:'flex', gap:8, flexWrap:'wrap', alignItems:'center'}}>
          <span className={`badge badge-${p.label}`}>
            {p.label === 'hate' ? '🔴' : '🟢'} {p.label.toUpperCase()}
          </span>
          <span className="result-conf">Conf: {(p.confidence * 100).toFixed(1)}%</span>
          <span className="result-conf">Severity: {(p.severity * 100).toFixed(1)}%</span>
          <span className="result-conf" style={{color:'var(--accent-light)'}}>
            ▲ {item.score}
          </span>
          {item.controversiality === 1 && (
            <span className="badge badge-warn">🔥 Controversial</span>
          )}
          {p.is_low_confidence && (
            <span className="badge badge-warn">⚠️ Low confidence</span>
          )}
        </div>
        
        {p.id && (
          <div className="feedback-controls" style={{display:'flex', gap:6, alignItems:'center'}}>
            {feedbackState === 'success' ? (
              <span style={{fontSize: 12, color: 'var(--safe)'}}>✓ Feedback saved</span>
            ) : feedbackState === 'loading' ? (
              <span style={{fontSize: 12, color: 'var(--text-muted)'}}>Saving...</span>
            ) : (
              <>
                <span style={{fontSize: 11, color: 'var(--text-muted)', marginRight: 4}}>Correct?</span>
                <button
                  className="btn"
                  style={{padding: '2px 6px', fontSize: 14, background: 'var(--bg-800)', minHeight: 'auto'}}
                  onClick={() => handleFeedback(p.label)}
                  title="Yes, this prediction is correct"
                >👍</button>
                <button
                  className="btn"
                  style={{padding: '2px 6px', fontSize: 14, background: 'var(--bg-800)', minHeight: 'auto'}}
                  onClick={() => handleFeedback(p.label === 'hate' ? 'safe' : 'hate')}
                  title="No, this prediction is wrong"
                >👎</button>
              </>
            )}
            {feedbackState === 'error' && (
              <span style={{fontSize: 12, color: 'var(--hate)'}}>Error</span>
            )}
          </div>
        )}
      </div>
      <div className="confidence-bar-wrap" style={{marginTop:8}}>
        <div className="confidence-bar-fill" style={{
          width:`${p.confidence*100}%`,
          background: p.label==='hate'
            ? 'linear-gradient(90deg, var(--hate), var(--warn))'
            : 'linear-gradient(90deg, var(--safe), var(--accent))'
        }} />
      </div>
    </div>
  )
}

export default function Analyzer() {
  const [subreddit,   setSubreddit]   = useState('')
  const [limit,       setLimit]       = useState(50)
  const [controvOnly, setControvOnly] = useState(false)
  const [loading,     setLoading]     = useState(false)
  const [error,       setError]       = useState('')
  const [results,     setResults]     = useState(null)
  const [suggestions, setSuggestions] = useState([])
  const [showSugg,    setShowSugg]    = useState(false)

  // Load available subreddits for autocomplete
  useEffect(() => {
    fetchSubreddits().then(data => setSuggestions(data.subreddits || []))
  }, [])

  const filtered = subreddit.length >= 2
    ? suggestions.filter(s => s.subreddit.includes(subreddit.toLowerCase())).slice(0, 8)
    : []

  async function handleAnalyze(sub = subreddit) {
    const s = sub.trim().replace(/^r\//i, '')
    if (!s) return
    setSubreddit(s)
    setShowSugg(false)
    setLoading(true)
    setError('')
    setResults(null)
    try {
      const params = new URLSearchParams({ subreddit: s, limit })
      if (controvOnly) params.set('controversial_only', 'true')
      const res = await fetch(`/api/analyze/reddit?${params}`)
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || data.hint || `HTTP ${res.status}`)
      setResults(data)
    } catch(e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const hateItems = results?.results?.filter(r => r.prediction.label === 'hate') ?? []
  const safeItems = results?.results?.filter(r => r.prediction.label === 'safe') ?? []

  return (
    <div>
      <div className="page-title">Live Reddit Analyzer</div>
      <div className="page-subtitle">
        Analyze any subreddit from the offline dataset — top comments ranked by score
      </div>

      {/* ── Input ── */}
      <div className="card" style={{marginBottom:24}}>
        {/* Subreddit input with autocomplete */}
        <div style={{position:'relative', marginBottom:12}}>
          <div className="input-wrapper" style={{marginBottom:0}}>
            <span style={{color:'var(--text-muted)', fontSize:14, whiteSpace:'nowrap'}}>r/</span>
            <input
              id="subreddit-input"
              className="input-field"
              placeholder="Type a subreddit name…"
              value={subreddit}
              onChange={e => { setSubreddit(e.target.value); setShowSugg(true) }}
              onFocus={() => setShowSugg(true)}
              onBlur={() => setTimeout(() => setShowSugg(false), 150)}
              onKeyDown={e => e.key === 'Enter' && handleAnalyze()}
            />
            <select
              className="input-field"
              style={{flex:'0 0 140px'}}
              value={limit}
              onChange={e => setLimit(Number(e.target.value))}
            >
              <option value={25}>25 comments</option>
              <option value={50}>50 comments</option>
              <option value={100}>100 comments</option>
              <option value={200}>200 comments</option>
            </select>
            <button
              id="analyze-btn"
              className="btn btn-primary"
              onClick={() => handleAnalyze()}
              disabled={loading || !subreddit.trim()}
            >
              {loading ? <><div className="spinner" /> Analyzing…</> : '🔍 Analyze'}
            </button>
          </div>

          {/* Autocomplete dropdown */}
          {showSugg && filtered.length > 0 && (
            <div style={{
              position:'absolute', top:'100%', left:0, right:0, zIndex:50,
              background:'var(--bg-700)', border:'1px solid var(--border)',
              borderRadius:'var(--radius-sm)', marginTop:4, overflow:'hidden',
            }}>
              {filtered.map(s => (
                <div
                  key={s.subreddit}
                  onMouseDown={() => handleAnalyze(s.subreddit)}
                  style={{
                    padding:'10px 16px', cursor:'pointer',
                    display:'flex', justifyContent:'space-between', alignItems:'center',
                    borderBottom:'1px solid var(--border)',
                    transition:'background 0.15s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background='var(--bg-600)'}
                  onMouseLeave={e => e.currentTarget.style.background='transparent'}
                >
                  <span style={{fontSize:14}}>r/{s.subreddit}</span>
                  <span style={{fontSize:12, color:'var(--text-muted)'}}>{s.count?.toLocaleString()} comments</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Options row */}
        <div style={{display:'flex', alignItems:'center', gap:16}}>
          <label style={{display:'flex', alignItems:'center', gap:8, fontSize:13, color:'var(--text-secondary)', cursor:'pointer'}}>
            <input
              type="checkbox"
              checked={controvOnly}
              onChange={e => setControvOnly(e.target.checked)}
              style={{accentColor:'var(--accent)'}}
            />
            Controversial only
          </label>
          <span style={{fontSize:12, color:'var(--text-muted)'}}>
            Data source: offline PostgreSQL · sorted by score ↓
          </span>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          ⚠️ {error}
          {error.includes('not in the dataset') && (
            <span style={{marginLeft:8, fontSize:12}}>→ try <strong>worldnews</strong>, <strong>AskReddit</strong>, or <strong>news</strong></span>
          )}
        </div>
      )}

      {/* ── Results ── */}
      {results && (
        <>
          <div className="stats-grid" style={{marginBottom:20}}>
            <div className="stat-card" style={{'--stat-accent':'var(--accent)'}}>
              <div className="stat-label">Total Analyzed</div>
              <div className="stat-value">{results.total_analyzed}</div>
            </div>
            <div className="stat-card" style={{'--stat-accent':'var(--hate)'}}>
              <div className="stat-label">Hate Content</div>
              <div className="stat-value" style={{color:'var(--hate)'}}>{results.hate_pct}%</div>
              <div className="stat-sub">{results.hate_count} items</div>
            </div>
            <div className="stat-card" style={{'--stat-accent':'var(--warn)'}}>
              <div className="stat-label">Avg Severity</div>
              <div className="stat-value">{results.avg_severity}</div>
            </div>
          </div>

          {hateItems.length > 0 && (
            <div className="card" style={{marginBottom:20}}>
              <div className="section-header">
                <span className="section-title">🔴 Hate Speech ({hateItems.length})</span>
              </div>
              {hateItems.map((item, i) => <ResultItem key={i} item={item} />)}
            </div>
          )}

          {safeItems.length > 0 && (
            <div className="card">
              <div className="section-header">
                <span className="section-title">🟢 Safe Content ({safeItems.length})</span>
              </div>
              {safeItems.map((item, i) => <ResultItem key={i} item={item} />)}
            </div>
          )}
        </>
      )}

      {!results && !loading && (
        <div className="empty-state">
          <div className="empty-icon">🔍</div>
          <h3>Enter a subreddit to begin</h3>
          <p>Fetches top-scored comments from the offline dataset and classifies them</p>
        </div>
      )}
    </div>
  )
}
