import { useState } from 'react'
import { ArrowLeft, Zap, CheckCircle, AlertCircle } from 'lucide-react'
import { api } from '../api/client'
import useStore from '../store/useStore'
import LoadingSpinner from './shared/LoadingSpinner'

const UPTIME_OPTIONS = ['99%', '99.9%', '99.99%', '99.999%']
const VISIBILITY_OPTIONS = ['public', 'internal', 'both']

export default function AutoModeScreen() {
  const {
    userInput, scopeResult, autoPilotInit,
    quickInputs, setQuickInputs,
    setSolution, setAnalysisBlocks, setScreen, setLoading, setError, loading,
  } = useStore()

  const [localInputs, setLocalInputs] = useState(quickInputs)
  const detections = autoPilotInit?.confirmed_detections || {}

  const setField = (field, value) => {
    const next = { ...localInputs, [field]: value }
    setLocalInputs(next)
    setQuickInputs(next)
  }

  const canGenerate = localInputs.users.trim() && localInputs.visibility && localInputs.uptime

  const handleGenerate = async () => {
    if (!canGenerate) return
    setLoading(true)
    setError(null)
    try {
      // Generate 7-block analysis JSON for display in SolutionOutput.
      const analysis = await api.guidedAnalysis(userInput, scopeResult, {})
      setAnalysisBlocks(analysis)
      const solution = await api.autoComplete(userInput, scopeResult, autoPilotInit, localInputs)
      setSolution(solution)
      setScreen('solution')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 animate-slide-up max-w-2xl mx-auto">
      <button
        onClick={() => setScreen('mode-selection')}
        className="flex items-center gap-1 text-muted hover:text-slate-300 text-sm transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Back
      </button>

      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-accent/10 text-accent">
          <Zap className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-slate-100">Auto Pilot Mode</h2>
          <p className="text-subtle text-sm">Just 3 quick answers — AI handles the rest</p>
        </div>
      </div>

      {autoPilotInit?.architecture_hint && (
        <div className="flex items-start gap-2 p-3 rounded-lg bg-primary/8 border border-primary/20">
          <AlertCircle className="w-4 h-4 text-primary mt-0.5 shrink-0" />
          <p className="text-xs text-slate-300 leading-relaxed">{autoPilotInit.architecture_hint}</p>
        </div>
      )}

      <div className="p-4 rounded-xl bg-card border border-border space-y-3">
        <h3 className="text-xs font-semibold text-muted uppercase tracking-wider">
          Confirmed Detections
        </h3>
        <div className="grid grid-cols-2 gap-3">
          <DetectionCard label="App Type" value={detections.app_type || scopeResult?.app_type} />
          <DetectionCard label="Architecture" value={detections.architecture_pattern} />
          <DetectionCard label="Session Store" value={detections.session_store} />
          <DetectionCard label="Deployment" value={detections.deployment_model} />
        </div>
        {detections.stack?.length > 0 && (
          <div>
            <span className="text-xs text-muted">Stack: </span>
            {detections.stack.map((t) => (
              <span key={t} className="chip bg-slate-800 text-slate-300 mr-1 text-[10px]">{t}</span>
            ))}
          </div>
        )}
      </div>

      <div className="p-4 rounded-xl bg-card border border-border space-y-5">
        <h3 className="text-xs font-semibold text-muted uppercase tracking-wider">
          Quick Fill-in (3 fields required)
        </h3>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-slate-200">
            Expected Users <span className="text-red-400">*</span>
          </label>
          <p className="text-xs text-muted">How many concurrent users do you expect at peak?</p>
          <input
            type="text"
            value={localInputs.users}
            onChange={(e) => setField('users', e.target.value)}
            placeholder="e.g., 500, 10000, 1M"
            className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-muted focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-all"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-slate-200">
            Application Visibility <span className="text-red-400">*</span>
          </label>
          <p className="text-xs text-muted">Will this application be accessible from the internet?</p>
          <div className="flex gap-2">
            {VISIBILITY_OPTIONS.map((opt) => (
              <button
                key={opt}
                onClick={() => setField('visibility', opt)}
                className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-all capitalize ${
                  localInputs.visibility === opt
                    ? 'bg-primary/20 border-primary/60 text-primary-light'
                    : 'bg-surface border-border text-subtle hover:border-border-light hover:text-slate-300'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-slate-200">
            Uptime Requirement <span className="text-red-400">*</span>
          </label>
          <p className="text-xs text-muted">What availability SLA do you need?</p>
          <div className="flex gap-2 flex-wrap">
            {UPTIME_OPTIONS.map((opt) => (
              <button
                key={opt}
                onClick={() => setField('uptime', opt)}
                className={`px-3 py-2 rounded-lg text-sm font-mono font-medium border transition-all ${
                  localInputs.uptime === opt
                    ? 'bg-primary/20 border-primary/60 text-primary-light'
                    : 'bg-surface border-border text-subtle hover:border-border-light hover:text-slate-300'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <LoadingSpinner message="Building your cloud architecture…" size="lg" />
      ) : (
        <button
          onClick={handleGenerate}
          disabled={!canGenerate || loading}
          className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-accent hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed text-slate-900 font-bold text-sm transition-all shadow-lg shadow-accent/20"
        >
          <CheckCircle className="w-4 h-4" />
          Generate Architecture
        </button>
      )}
    </div>
  )
}

function DetectionCard({ label, value }) {
  return (
    <div className="bg-surface rounded-lg px-3 py-2">
      <div className="text-[10px] text-muted uppercase tracking-wide">{label}</div>
      <div className="text-sm font-medium text-slate-200 mt-0.5 capitalize">{value || '—'}</div>
    </div>
  )
}
