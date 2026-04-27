import { Zap, Layers, Settings, ChevronRight, ArrowLeft, CheckCircle } from 'lucide-react'
import useStore from '../store/useStore'
import { api } from '../api/client'

const MODE_CONFIG = {
  AUTO: {
    icon: Zap,
    color: 'text-accent',
    border: 'border-accent/30 hover:border-accent/70',
    bg: 'bg-accent/5',
    selectedBg: 'bg-accent/10 border-accent/70',
    label: 'Auto Pilot',
    tagline: 'Fastest path to your architecture',
    description: 'Answer just 3 quick questions. AI fills in the rest using best-practice defaults.',
    timeEst: '~30 seconds',
  },
  GUIDED: {
    icon: Layers,
    color: 'text-primary-light',
    border: 'border-primary/30 hover:border-primary/70',
    bg: 'bg-primary/5',
    selectedBg: 'bg-primary/10 border-primary/70',
    label: 'Guided Mode',
    tagline: 'Structured 7-block discovery',
    description: 'Walk through 7 blocks of business-focused questions. Skip anything you don\'t know.',
    timeEst: '~3 minutes',
  },
  EXPERT: {
    icon: Settings,
    color: 'text-yellow-400',
    border: 'border-yellow-600/30 hover:border-yellow-500/60',
    bg: 'bg-yellow-900/10',
    selectedBg: 'bg-yellow-900/20 border-yellow-500/60',
    label: 'Expert Mode',
    tagline: 'Full schema control',
    description: 'Edit the architecture JSON directly. For users who know exactly what they need.',
    timeEst: 'Self-paced',
  },
}

export default function ModeSelection() {
  const { scopeResult, modeResult, selectedMode, setSelectedMode, setScreen, setLoading, setError, setAutoPilotInit, userInput, loading } =
    useStore()

  const recommended = modeResult?.recommended_mode || 'GUIDED'

  const handleContinue = async () => {
    const mode = selectedMode || recommended
    setSelectedMode(mode)

    if (mode === 'AUTO') {
      setLoading(true)
      setError(null)
      try {
        const init = await api.autoInit(userInput, scopeResult)
        setAutoPilotInit(init)
        setScreen('auto-mode')
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    } else if (mode === 'GUIDED') {
      setScreen('guided-mode')
    } else {
      setScreen('expert-mode')
    }
  }

  return (
    <div className="space-y-6 animate-slide-up">
      <button
        onClick={() => setScreen('entry')}
        className="flex items-center gap-1 text-muted hover:text-slate-300 text-sm transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Back
      </button>

      <div>
        <h2 className="text-2xl font-bold text-slate-100">Choose your design mode</h2>
        <p className="text-subtle text-sm mt-1">AI recommends <strong className="text-slate-200">{MODE_CONFIG[recommended]?.label}</strong> — {modeResult?.reasoning}</p>
      </div>

      {scopeResult && (
        <div className="p-4 rounded-xl bg-card border border-border">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Scope Analysis</p>
          <div className="flex flex-wrap gap-2">
            <Chip label={`Type: ${scopeResult.app_type}`} color="indigo" />
            <Chip label={`Scale: ${scopeResult.scale_hint}`} color="blue" />
            <Chip label={`Domain: ${scopeResult.domain}`} color="purple" />
            {scopeResult.stack?.map((tech) => (
              <Chip key={tech} label={tech} color="gray" />
            ))}
            {scopeResult.reasoning?.slice(0, 4).map((sig) => (
              <Chip key={sig} label={sig} color="green" small />
            ))}
          </div>
          <div className="mt-2 flex items-center gap-2">
            <div className="h-1 flex-1 bg-border rounded-full">
              <div
                className="h-1 bg-primary rounded-full"
                style={{ width: `${Math.round((scopeResult.confidence_score || 0) * 100)}%` }}
              />
            </div>
            <span className="text-xs text-muted">{Math.round((scopeResult.confidence_score || 0) * 100)}% confidence</span>
          </div>
        </div>
      )}

      <div className="grid gap-3">
        {Object.entries(MODE_CONFIG).map(([mode, cfg]) => {
          const Icon = cfg.icon
          const isSelected = (selectedMode || recommended) === mode
          const isRec = recommended === mode
          return (
            <button
              key={mode}
              onClick={() => setSelectedMode(mode)}
              className={`flex items-start gap-4 p-4 rounded-xl border text-left transition-all ${
                isSelected ? cfg.selectedBg : `${cfg.bg} ${cfg.border} border`
              }`}
            >
              <div className={`mt-0.5 p-2 rounded-lg bg-surface/60 ${cfg.color}`}>
                <Icon className="w-5 h-5" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-100 text-sm">{cfg.label}</span>
                  {isRec && (
                    <span className="chip bg-primary/20 text-primary-light text-[10px]">Recommended</span>
                  )}
                  <span className="ml-auto text-xs text-muted">{cfg.timeEst}</span>
                </div>
                <p className="text-xs font-medium text-muted mt-0.5">{cfg.tagline}</p>
                <p className="text-xs text-subtle mt-1 leading-relaxed">{cfg.description}</p>
              </div>
              <CheckCircle
                className={`w-5 h-5 shrink-0 mt-0.5 transition-opacity ${isSelected ? 'text-primary opacity-100' : 'opacity-0'}`}
              />
            </button>
          )
        })}
      </div>

      <button
        onClick={handleContinue}
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-primary hover:bg-primary-hover disabled:opacity-50 text-white font-semibold text-sm transition-all shadow-lg shadow-primary/20"
      >
        {loading ? (
          <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Loading…</>
        ) : (
          <>Continue with {MODE_CONFIG[selectedMode || recommended]?.label} <ChevronRight className="w-4 h-4" /></>
        )}
      </button>
    </div>
  )
}

function Chip({ label, color, small }) {
  const colors = {
    indigo: 'bg-indigo-900/40 text-indigo-300',
    blue: 'bg-blue-900/40 text-blue-300',
    purple: 'bg-purple-900/40 text-purple-300',
    green: 'bg-green-900/40 text-green-300',
    gray: 'bg-slate-800 text-slate-300',
  }
  return (
    <span className={`chip ${colors[color] || colors.gray} ${small ? 'text-[10px]' : 'text-xs'}`}>
      {label}
    </span>
  )
}
