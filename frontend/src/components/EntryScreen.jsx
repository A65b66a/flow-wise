import { useState } from 'react'
import { ArrowRight, Zap, Layers, Settings } from 'lucide-react'
import { api } from '../api/client'
import useStore from '../store/useStore'
import LoadingSpinner from './shared/LoadingSpinner'

const EXAMPLES = [
  'I want to build an e-commerce platform for 50,000 users with a React frontend and Node.js backend',
  'A real-time chat application with WebSocket support, user authentication, and message history',
  'Internal HR tool for 200 employees with document management and approval workflows',
  'IoT sensor data pipeline that ingests 1 million events per day and stores time-series metrics',
]

export default function EntryScreen() {
  const [text, setText] = useState('')
  const { setUserInput, setScopeResult, setModeResult, setScreen, setLoading, setError, loading } =
    useStore()

  const handleAnalyze = async () => {
    const trimmed = text.trim()
    if (!trimmed) return

    setLoading(true)
    setError(null)
    try {
      const scope = await api.analyzeScope(trimmed)
      if (scope.status === 'failed') {
        setError(scope.reasoning?.[0] || scope.message)
        return
      }
      const mode = await api.selectMode(trimmed, scope)
      setUserInput(trimmed)
      setScopeResult(scope)
      setModeResult(mode)
      setScreen('mode-selection')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleAnalyze()
  }

  return (
    <div className="flex flex-col items-center gap-8 pt-12 animate-slide-up">
      <div className="text-center space-y-3 max-w-xl">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-medium mb-2">
          <Zap className="w-3 h-3" />
          AI-Powered Architecture Design
        </div>
        <h1 className="text-4xl font-bold text-slate-100 tracking-tight">
          Describe your application
        </h1>
        <p className="text-subtle text-base">
          Tell us what you're building in plain English — we'll design the cloud architecture for you.
        </p>
      </div>

      <div className="w-full max-w-2xl space-y-3">
        <div className="relative">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g. I'm building a healthcare platform for patient records and appointment booking, expected 10,000 users, needs to be HIPAA compliant..."
            rows={5}
            className="w-full bg-card border border-border rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-muted resize-none focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-all"
          />
          <div className="absolute bottom-3 right-3 text-xs text-muted font-mono">
            ⌘+Enter
          </div>
        </div>

        <button
          onClick={handleAnalyze}
          disabled={!text.trim() || loading}
          className="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-primary hover:bg-primary-hover disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold text-sm transition-all duration-200 shadow-lg shadow-primary/20"
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Analyzing…
            </>
          ) : (
            <>
              Analyze & Design Architecture
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>

      {loading && (
        <LoadingSpinner message="Analyzing your application with AI…" />
      )}

      <div className="w-full max-w-2xl">
        <p className="text-xs text-muted mb-3 text-center">Try an example:</p>
        <div className="grid gap-2">
          {EXAMPLES.map((ex, i) => (
            <button
              key={i}
              onClick={() => setText(ex)}
              className="text-left text-xs text-subtle hover:text-slate-200 bg-card/50 hover:bg-card border border-border hover:border-border-light rounded-lg px-3 py-2 transition-all leading-relaxed"
            >
              "{ex}"
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 w-full max-w-2xl mt-4">
        {[
          { icon: Zap, label: 'Auto Pilot', desc: 'Quick 3-question flow' },
          { icon: Layers, label: 'Guided', desc: '7-block structured wizard' },
          { icon: Settings, label: 'Expert', desc: 'Full schema control' },
        ].map(({ icon: Icon, label, desc }) => (
          <div key={label} className="p-3 rounded-lg border border-border bg-card/30 text-center">
            <Icon className="w-5 h-5 text-primary mx-auto mb-1" />
            <div className="text-xs font-semibold text-slate-200">{label}</div>
            <div className="text-xs text-muted">{desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
