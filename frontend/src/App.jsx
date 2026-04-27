import useStore from './store/useStore'
import EntryScreen from './components/EntryScreen'
import ModeSelection from './components/ModeSelection'
import AutoModeScreen from './components/AutoModeScreen'
import GuidedModeScreen from './components/GuidedModeScreen'
import ExpertModeScreen from './components/ExpertModeScreen'
import SolutionOutput from './components/SolutionOutput'
import ErrorBanner from './components/shared/ErrorBanner'

const SCREENS = {
  entry: EntryScreen,
  'mode-selection': ModeSelection,
  'auto-mode': AutoModeScreen,
  'guided-mode': GuidedModeScreen,
  'expert-mode': ExpertModeScreen,
  solution: SolutionOutput,
}

export default function App() {
  const screen = useStore((s) => s.screen)
  const error = useStore((s) => s.error)
  const setError = useStore((s) => s.setError)

  const Screen = SCREENS[screen] || EntryScreen

  return (
    <div className="min-h-screen bg-surface text-slate-100">
      <header className="border-b border-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-white font-bold text-sm">
            CA
          </div>
          <span className="font-semibold text-slate-100 tracking-tight">
            Cloud Architecture Generator
          </span>
        </div>
        <div className="text-xs text-muted font-mono">v1.0.0</div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        {error && (
          <ErrorBanner message={error} onClose={() => setError(null)} />
        )}
        <div className="screen-enter">
          <Screen />
        </div>
      </main>
    </div>
  )
}
