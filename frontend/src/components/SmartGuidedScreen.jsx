import { useState, useEffect } from 'react'
import { ArrowLeft, ArrowRight, Zap } from 'lucide-react'
import { api } from '../api/client'
import useStore from '../store/useStore'
import LoadingSpinner from './shared/LoadingSpinner'

export default function SmartGuidedScreen() {
  const {
    userInput, scopeResult,
    smartQuestions, setSmartQuestions,
    smartAnswers, setSmartAnswers,
    setSolution, setAnalysisBlocks, setScreen, setLoading, setError, loading,
  } = useStore()

  const [answers, setAnswers] = useState(smartAnswers || {})
  const [fetching, setFetching] = useState(false)

  useEffect(() => {
    if (!smartQuestions) {
      loadQuestions()
    }
  }, [])

  const loadQuestions = async () => {
    setFetching(true)
    setError(null)
    try {
      const data = await api.smartGuidedQuestions(userInput, scopeResult)
      setSmartQuestions(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setFetching(false)
    }
  }

  const setAnswer = (id, value) => setAnswers((prev) => ({ ...prev, [id]: value }))

  const handleGenerate = async () => {
    setSmartAnswers(answers)
    setLoading(true)
    setError(null)
    try {
      const solution = await api.smartGuidedComplete(userInput, scopeResult, answers)
      setSolution(solution)
      if (solution.analysis_blocks) setAnalysisBlocks(solution.analysis_blocks)
      setScreen('solution')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const requiredAnswered = smartQuestions?.questions
    ?.filter((q) => q.required)
    .every((q) => answers[q.id] !== undefined && answers[q.id] !== '')

  if (loading) {
    return (
      <div className="flex flex-col items-center pt-16">
        <LoadingSpinner message="Building your architecture…" size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-slide-up max-w-2xl mx-auto">
      <div className="flex items-center gap-3">
        <button
          onClick={() => setScreen('mode-selection')}
          className="flex items-center gap-1 text-muted hover:text-slate-300 text-sm transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        <div className="flex-1" />
        <div className="flex items-center gap-2 text-accent">
          <Zap className="w-4 h-4" />
          <span className="text-sm font-medium">Smart Guided Mode</span>
        </div>
      </div>

      {fetching ? (
        <LoadingSpinner message="Preparing questions for your project…" />
      ) : smartQuestions ? (
        <div className="space-y-6">
          <div>
            <h2 className="text-xl font-bold text-slate-100">{smartQuestions.title}</h2>
            <p className="text-subtle text-sm mt-1">{smartQuestions.description}</p>
          </div>

          <div className="space-y-4">
            {smartQuestions.questions?.map((q) => (
              <QuestionField key={q.id} q={q} value={answers[q.id]} onChange={(v) => setAnswer(q.id, v)} />
            ))}
          </div>

          <button
            onClick={handleGenerate}
            disabled={!requiredAnswered || loading}
            className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-primary hover:bg-primary-hover disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold text-sm transition-all"
          >
            Generate Architecture
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      ) : null}
    </div>
  )
}

function QuestionField({ q, value, onChange }) {
  return (
    <div className="space-y-2 p-4 rounded-xl bg-card border border-border">
      <div className="space-y-1">
        <label className="text-sm font-medium text-slate-200">
          {q.text}
          {q.required && <span className="text-red-400 ml-1">*</span>}
        </label>
        <p className="text-xs text-muted flex items-start gap-1">
          <span className="text-primary font-semibold mt-0.5">Why:</span>
          {q.why}
        </p>
      </div>

      {q.type === 'text' || q.type === 'number' ? (
        <input
          type={q.type}
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder={q.placeholder}
          className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-muted focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-all"
        />
      ) : q.type === 'select' ? (
        <div className="flex flex-col gap-2">
          {q.options?.map((opt) => (
            <button
              key={opt}
              onClick={() => onChange(opt)}
              className={`text-left px-3 py-2 rounded-lg text-sm border transition-all ${
                value === opt
                  ? 'bg-primary/20 border-primary/60 text-primary-light font-medium'
                  : 'bg-surface border-border text-subtle hover:border-border-light hover:text-slate-300'
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
      ) : q.type === 'multiselect' ? (
        <div className="flex flex-col gap-2">
          {q.options?.map((opt) => {
            const selected = Array.isArray(value) ? value.includes(opt) : false
            return (
              <button
                key={opt}
                onClick={() => {
                  const arr = Array.isArray(value) ? [...value] : []
                  onChange(selected ? arr.filter((x) => x !== opt) : [...arr, opt])
                }}
                className={`text-left px-3 py-2 rounded-lg text-sm border transition-all ${
                  selected
                    ? 'bg-primary/20 border-primary/60 text-primary-light font-medium'
                    : 'bg-surface border-border text-subtle hover:border-border-light hover:text-slate-300'
                }`}
              >
                {opt}
              </button>
            )
          })}
        </div>
      ) : q.type === 'boolean' ? (
        <div className="flex gap-2">
          {['Yes', 'No'].map((opt) => (
            <button
              key={opt}
              onClick={() => onChange(opt === 'Yes')}
              className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-all ${
                (opt === 'Yes' ? value === true : value === false)
                  ? 'bg-primary/20 border-primary/60 text-primary-light'
                  : 'bg-surface border-border text-subtle hover:border-border-light hover:text-slate-300'
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
