import { useState } from 'react'
import {
  RotateCcw, Download, CheckCircle, AlertTriangle, Code, Brain, LayoutGrid, ChevronDown, ChevronUp,
} from 'lucide-react'
import useStore from '../store/useStore'
import CytoscapeGraph from './CytoscapeGraph'

const TABS = [
  { id: 'summary', label: 'Architecture Summary', icon: LayoutGrid },
  { id: 'reasoning', label: 'Why This Architecture', icon: Brain },
  { id: 'json', label: 'JSON Configuration', icon: Code },
  { id: 'analysis', label: '7-Block Analysis', icon: Code },
]

export default function SolutionOutput() {
  const { solution, analysisBlocks, reset } = useStore()
  const [activeTab, setActiveTab] = useState('summary')
  const [jsonExpanded, setJsonExpanded] = useState(false)
  const [analysisExpanded, setAnalysisExpanded] = useState(false)

  if (!solution) {
    return (
      <div className="text-center py-16 text-muted">
        <p>No solution generated yet.</p>
        <button onClick={reset} className="mt-4 text-primary hover:underline text-sm">
          Start over
        </button>
      </div>
    )
  }

  const handleDownload = () => {
    const blob = new Blob([JSON.stringify(solution, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `architecture-${solution.template_id}-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6 animate-slide-up">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle className="w-5 h-5 text-green-400" />
            <h2 className="text-xl font-bold text-slate-100">Architecture Generated</h2>
          </div>
          <p className="text-subtle text-sm">
            {solution.template_name} — {solution.summary?.deployment_complexity} complexity
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={handleDownload}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-border text-subtle hover:text-slate-200 hover:border-border-light text-sm transition-all"
          >
            <Download className="w-4 h-4" /> Export
          </button>
          <button
            onClick={reset}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-border text-subtle hover:text-slate-200 hover:border-border-light text-sm transition-all"
          >
            <RotateCcw className="w-4 h-4" /> New
          </button>
        </div>
      </div>

      <div className="flex gap-1 p-1 bg-card rounded-xl border border-border">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-sm font-medium transition-all ${
              activeTab === id
                ? 'bg-primary/20 text-primary-light border border-primary/30'
                : 'text-muted hover:text-slate-300'
            }`}
          >
            <Icon className="w-4 h-4" />
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </div>

      <div className="animate-fade-in">
        {activeTab === 'summary' && <SummaryPanel solution={solution} />}
        {activeTab === 'reasoning' && <ReasoningPanel solution={solution} />}
        {activeTab === 'json' && (
          <JsonPanel
            solution={solution}
            expanded={jsonExpanded}
            onToggle={() => setJsonExpanded((e) => !e)}
          />
        )}
        {activeTab === 'analysis' && (
          <AnalysisPanel
            analysis={solution?.analysis_blocks || analysisBlocks}
            expanded={analysisExpanded}
            onToggle={() => setAnalysisExpanded((e) => !e)}
          />
        )}
      </div>

      <div>
        <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
          <LayoutGrid className="w-4 h-4 text-primary" /> Architecture Diagram
        </h3>
        <CytoscapeGraph elements={solution.cytoscape_elements} />
      </div>
    </div>
  )
}

function SummaryPanel({ solution }) {
  const s = solution.summary
  const req = solution.requirements
  return (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-2 gap-3">
        <MetricCard label="Architecture Type" value={s.architecture_type} color="primary" />
        <MetricCard label="Est. Monthly Cost" value={s.estimated_monthly_cost} color="green" />
        <MetricCard label="Deployment Complexity" value={s.deployment_complexity} color={s.deployment_complexity === 'High' ? 'red' : s.deployment_complexity === 'Medium' ? 'yellow' : 'green'} />
        <MetricCard label="Uptime Target" value={req?.availability?.uptime_requirement || 'N/A'} color="blue" />
      </div>

      {s.key_highlights?.length > 0 && (
        <div className="p-4 rounded-xl bg-card border border-border">
          <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Key Highlights</h4>
          <ul className="space-y-2">
            {s.key_highlights.map((h, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                <CheckCircle className="w-4 h-4 text-green-400 shrink-0 mt-0.5" />
                {h}
              </li>
            ))}
          </ul>
        </div>
      )}

      {s.components?.length > 0 && (
        <div className="p-4 rounded-xl bg-card border border-border">
          <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Components</h4>
          <div className="flex flex-wrap gap-2">
            {s.components.map((c) => (
              <span key={c} className="chip bg-primary/10 text-primary-light border border-primary/20 text-xs">
                {c}
              </span>
            ))}
          </div>
        </div>
      )}

      {req && (
        <div className="p-4 rounded-xl bg-card border border-border space-y-3">
          <h4 className="text-xs font-semibold text-muted uppercase tracking-wider">Requirements Summary</h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
            <ReqRow label="Concurrent Users" value={req.scale?.concurrent_users?.toLocaleString()} />
            <ReqRow label="RPS (est.)" value={req.scale?.requests_per_second?.toLocaleString()} />
            <ReqRow label="Multi-AZ" value={req.availability?.multi_az ? '✓ Yes' : '✗ No'} />
            <ReqRow label="CDN" value={req.network?.cdn_required ? '✓ Yes' : '✗ No'} />
            <ReqRow label="Data Class" value={req.security?.data_classification} />
            <ReqRow label="Internet Facing" value={req.network?.internet_facing ? '✓ Yes' : '✗ No'} />
          </div>
          {req.security?.compliance?.length > 0 && (
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-3.5 h-3.5 text-yellow-400" />
              <span className="text-xs text-yellow-300">
                Compliance: {req.security.compliance.join(', ')}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ReasoningPanel({ solution }) {
  const r = solution.reasoning
  return (
    <div className="space-y-4">
      <div className="p-4 rounded-xl bg-card border border-border">
        <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">Why This Template</h4>
        <p className="text-sm text-slate-300 leading-relaxed">{r.template_selection}</p>
      </div>

      {r.component_choices?.length > 0 && (
        <div className="p-4 rounded-xl bg-card border border-border">
          <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Component Decisions</h4>
          <ul className="space-y-2.5">
            {r.component_choices.map((c, i) => (
              <li key={i} className="text-sm text-slate-300 leading-relaxed flex items-start gap-2">
                <span className="text-primary font-mono text-xs shrink-0 mt-0.5">{String(i + 1).padStart(2, '0')}</span>
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}

      {r.trade_offs?.length > 0 && (
        <div className="p-4 rounded-xl bg-card border border-border">
          <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Trade-offs</h4>
          <ul className="space-y-2">
            {r.trade_offs.map((t, i) => (
              <li key={i} className="text-sm text-subtle leading-relaxed flex items-start gap-2">
                <AlertTriangle className="w-3.5 h-3.5 text-yellow-500 shrink-0 mt-0.5" />
                {t}
              </li>
            ))}
          </ul>
        </div>
      )}

      {r.alternatives_considered?.length > 0 && (
        <div className="p-4 rounded-xl bg-card border border-border">
          <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Alternatives Considered</h4>
          <ul className="space-y-2">
            {r.alternatives_considered.map((a, i) => (
              <li key={i} className="text-sm text-subtle leading-relaxed">{a}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function JsonPanel({ solution, expanded, onToggle }) {
  const [copied, setCopied] = useState(false)
  const jsonStr = JSON.stringify(solution.configuration, null, 2)
  const preview = jsonExpanded(expanded, jsonStr)

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(solution, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="p-4 rounded-xl bg-card border border-border space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-muted uppercase tracking-wider">Configuration JSON</h4>
        <div className="flex gap-2">
          <button
            onClick={handleCopy}
            className="text-xs text-primary hover:text-primary-light transition-colors"
          >
            {copied ? '✓ Copied' : 'Copy All'}
          </button>
          <button
            onClick={onToggle}
            className="flex items-center gap-1 text-xs text-muted hover:text-slate-300 transition-colors"
          >
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            {expanded ? 'Collapse' : 'Expand'}
          </button>
        </div>
      </div>
      <div className="overflow-auto max-h-96 rounded-lg bg-surface p-3">
        <pre className="json-code">{preview}</pre>
      </div>
      {!expanded && jsonStr.length > 1200 && (
        <button onClick={onToggle} className="text-xs text-primary hover:text-primary-light transition-colors">
          Show full configuration ({jsonStr.length.toLocaleString()} chars)…
        </button>
      )}
    </div>
  )
}

function AnalysisPanel({ analysis, expanded, onToggle }) {
  const [copied, setCopied] = useState(false)
  const jsonStr = JSON.stringify(analysis || {}, null, 2)
  const preview = jsonExpanded(expanded, jsonStr)

  const handleCopy = () => {
    navigator.clipboard.writeText(jsonStr)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (!analysis) {
    return (
      <div className="p-4 rounded-xl bg-card border border-border text-sm text-muted">
        No analysis blocks were generated for this run.
      </div>
    )
  }

  return (
    <div className="p-4 rounded-xl bg-card border border-border space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-muted uppercase tracking-wider">7-Block Analysis JSON</h4>
        <div className="flex gap-2">
          <button
            onClick={handleCopy}
            className="text-xs text-primary hover:text-primary-light transition-colors"
          >
            {copied ? '✓ Copied' : 'Copy'}
          </button>
          <button
            onClick={onToggle}
            className="flex items-center gap-1 text-xs text-muted hover:text-slate-300 transition-colors"
          >
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            {expanded ? 'Collapse' : 'Expand'}
          </button>
        </div>
      </div>
      <div className="overflow-auto max-h-96 rounded-lg bg-surface p-3">
        <pre className="json-code">{preview}</pre>
      </div>
      {!expanded && jsonStr.length > 1200 && (
        <button onClick={onToggle} className="text-xs text-primary hover:text-primary-light transition-colors">
          Show full analysis ({jsonStr.length.toLocaleString()} chars)…
        </button>
      )}
    </div>
  )
}

function jsonExpanded(expanded, jsonStr) {
  if (expanded) return jsonStr
  const lines = jsonStr.split('\n')
  if (lines.length <= 30) return jsonStr
  return lines.slice(0, 30).join('\n') + '\n  // … expand to see more'
}

function MetricCard({ label, value, color }) {
  const colors = {
    primary: 'text-primary-light bg-primary/5 border-primary/20',
    green: 'text-green-300 bg-green-900/10 border-green-800/30',
    red: 'text-red-300 bg-red-900/10 border-red-800/30',
    yellow: 'text-yellow-300 bg-yellow-900/10 border-yellow-800/30',
    blue: 'text-blue-300 bg-blue-900/10 border-blue-800/30',
  }
  return (
    <div className={`p-3 rounded-xl border ${colors[color] || colors.primary}`}>
      <div className="text-[10px] text-muted uppercase tracking-wide mb-1">{label}</div>
      <div className="text-sm font-semibold">{value || '—'}</div>
    </div>
  )
}

function ReqRow({ label, value }) {
  return (
    <div>
      <div className="text-muted mb-0.5">{label}</div>
      <div className="text-slate-300 font-medium">{value || '—'}</div>
    </div>
  )
}
