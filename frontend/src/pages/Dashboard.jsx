import { useState, useEffect } from 'react'
import { api } from '../api'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts'

const PIE_COLORS = ['#ef4444', '#22c55e']

const CUSTOM_TOOLTIP = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background:'var(--bg-700)', border:'1px solid var(--border)', borderRadius:8, padding:'10px 14px', fontSize:13 }}>
      <p style={{ color:'var(--text-secondary)', marginBottom:4 }}>{label}</p>
      {payload.map(p => (
        <p key={p.name} style={{ color: p.color, fontWeight:600 }}>{p.name}: {p.value}{p.name.includes('%') ? '%' : ''}</p>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const [stats,    setStats]    = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState('')

  useEffect(() => {
    api.getAnalytics()
      .then(r => setStats(r.data))
      .catch(e => setError(e.response?.data?.error || 'Could not connect to API. Is the backend running?'))
      .finally(() => setLoading(false))
  }, [])

  const subredditChartData = stats?.subreddits?.map(s => ({
    name: `r/${s.subreddit}`,
    'Total':    s.total,
    'Hate %':   s.hate_pct,
  })) ?? []

  const pieData = stats ? [
    { name: 'Hate',  value: stats.hate_count  },
    { name: 'Safe',  value: stats.safe_count  },
  ] : []

  return (
    <div>
      <div className="page-title">Dashboard</div>
      <div className="page-subtitle">Overview of moderation activity and model analytics</div>

      {error && <div className="error-banner">⚠️ {error}</div>}

      {loading ? (
        <div className="empty-state"><div className="spinner" style={{margin:'0 auto'}} /></div>
      ) : stats ? (
        <>
          {/* ── KPI Cards ── */}
          <div className="stats-grid">
            <div className="stat-card" style={{'--stat-accent':'var(--accent)'}}>
              <div className="stat-label">Total Analyzed</div>
              <div className="stat-value">{stats.total_analyzed.toLocaleString()}</div>
              <div className="stat-sub">posts & comments</div>
            </div>
            <div className="stat-card" style={{'--stat-accent':'var(--hate)'}}>
              <div className="stat-label">Hate Content</div>
              <div className="stat-value" style={{color:'var(--hate)'}}>{stats.hate_percentage}%</div>
              <div className="stat-sub">{stats.hate_count.toLocaleString()} flagged</div>
            </div>
            <div className="stat-card" style={{'--stat-accent':'var(--safe)'}}>
              <div className="stat-label">Safe Content</div>
              <div className="stat-value" style={{color:'var(--safe)'}}>{(100 - stats.hate_percentage).toFixed(1)}%</div>
              <div className="stat-sub">{stats.safe_count.toLocaleString()} clean</div>
            </div>
            <div className="stat-card" style={{'--stat-accent':'var(--warn)'}}>
              <div className="stat-label">Avg Severity</div>
              <div className="stat-value" style={{color:'var(--warn)'}}>{stats.avg_severity}</div>
              <div className="stat-sub">normalized 0–1</div>
            </div>
            <div className="stat-card" style={{'--stat-accent':'var(--text-muted)'}}>
              <div className="stat-label">Low Confidence</div>
              <div className="stat-value">{stats.low_confidence}</div>
              <div className="stat-sub">needs review</div>
            </div>
          </div>

          {/* ── Charts ── */}
          <div className="charts-grid">
            <div className="card">
              <div className="section-header">
                <span className="section-title">Hate % by Subreddit</span>
              </div>
              {subredditChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={subredditChartData}>
                    <XAxis dataKey="name" tick={{ fill:'var(--text-muted)', fontSize:11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill:'var(--text-muted)', fontSize:11 }} axisLine={false} tickLine={false} />
                    <Tooltip content={<CUSTOM_TOOLTIP />} />
                    <Bar dataKey="Hate %" fill="var(--hate)" radius={[4,4,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="empty-state" style={{padding:'40px 0'}}>
                  <p>No subreddit data yet.<br/>Run the Live Analyzer first.</p>
                </div>
              )}
            </div>

            <div className="card">
              <div className="section-header">
                <span className="section-title">Content Split</span>
              </div>
              {pieData.some(d => d.value > 0) ? (
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={90}
                         dataKey="value" paddingAngle={3}>
                      {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i]} />)}
                    </Pie>
                    <Tooltip content={<CUSTOM_TOOLTIP />} />
                    <Legend iconType="circle" wrapperStyle={{ fontSize:13, color:'var(--text-secondary)' }} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="empty-state" style={{padding:'40px 0'}}><p>No predictions stored yet.</p></div>
              )}
            </div>
          </div>

          {/* ── By Content Type ── */}
          {stats.by_content_type?.length > 0 && (
            <div className="card">
              <div className="section-header">
                <span className="section-title">Posts vs Comments</span>
              </div>
              <div style={{ display:'flex', gap:24, flexWrap:'wrap' }}>
                {stats.by_content_type.map(t => (
                  <div key={t.content_type} style={{ flex:1, minWidth:180 }}>
                    <div style={{ fontSize:13, color:'var(--text-secondary)', marginBottom:8, textTransform:'capitalize' }}>
                      {t.content_type}s
                    </div>
                    <div style={{ fontSize:24, fontWeight:800 }}>{t.total}</div>
                    <div style={{ fontSize:12, color:'var(--hate)', marginBottom:10 }}>
                      {t.hate_pct}% hate
                    </div>
                    <div className="confidence-bar-wrap">
                      <div className="confidence-bar-fill"
                        style={{ width:`${t.hate_pct}%`, background:`linear-gradient(90deg, var(--hate), var(--warn))` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="empty-state">
          <div className="empty-icon">📊</div>
          <h3>No data yet</h3>
          <p>Analyze a subreddit to populate the dashboard</p>
        </div>
      )}
    </div>
  )
}
