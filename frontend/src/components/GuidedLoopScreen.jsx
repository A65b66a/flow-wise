import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { api } from '../api/client'
import useStore from '../store/useStore'
import LoadingSpinner from './shared/LoadingSpinner'

export default function GuidedLoopScreen() {
  const {
    userInput,
    scopeResult,
    setSolution,
    setAnalysisBlocks,
    setScreen,
    setError,
    loading,
  } = useStore()

  const [sessionId, setSessionId] = useState(null)
  const [question, setQuestion] = useState(null)
  const [questionNumber, setQuestionNumber] = useState(1)
  const [submitting, setSubmitting] = useState(false)
  const [generating, setGenerating] = useState(false)

  const [value, setValue] = useState('')
  const [multi, setMulti] = useState([])

  const isMulti = question?.type === 'multi_choice'
  const isSingle = question?.type === 'single_choice'
  const isNumber = question?.type === 'number'
  const isText = question?.type === 'text'

  const options = useMemo(() => question?.options || [], [question])

  const canSubmit = useMemo(() => {
    if (!question) return false
    if (isMulti) return multi.length > 0
    if (isSingle) return value !== ''
    if (isNumber) return String(value || '').trim().length > 0
    if (isText) return String(value || '').trim().length > 0
    return false
  }, [question, isMulti, isSingle, isNumber, isText, value, multi])

  const start = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const res = await api.guidedLoopStart(userInput, scopeResult, 10)
      setSessionId(res.session_id)
      if (res.status === 'complete' && res.analysis_blocks) {
        await finalizeSolution(res.session_id)
        return
      }
      setQuestion(res.question)
      setQuestionNumber(res.question_number || 1)
      setValue('')
      setMulti([])
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const finalizeSolution = async (sid) => {
    setGenerating(true)
    try {
      const session = await api.guidedLoopSession(sid)
      const solution = await api.smartGuidedComplete(userInput, scopeResult, session.answers || {})
      setSolution(solution)
      if (solution.analysis_blocks) setAnalysisBlocks(solution.analysis_blocks)
      setScreen('solution')
    } catch (err) {
      setError(err.message)
    } finally {
      setGenerating(false)
    }
  }

  useEffect(() => {
    start()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const submit = async () => {
    if (!sessionId || !question || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      const payloadValue = isMulti ? multi : value
      const res = await api.guidedLoopAnswer(sessionId, question.field, payloadValue)
      if (res.status === 'complete') {
        await finalizeSolution(res.session_id)
        return
      }
      setQuestion(res.question)
      setQuestionNumber(res.question_number || (questionNumber + 1))
      setValue('')
      setMulti([])
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const toggleMulti = (opt) => {
    setMulti((prev) => (prev.includes(opt) ? prev.filter((x) => x !== opt) : [...prev, opt]))
  }

  if (generating || loading) {
    return (
      <div className="flex flex-col items-center pt-16">
        <LoadingSpinner message="Building your cloud architecture…" size="lg" />
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto animate-slide-up">
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => setScreen('mode-selection')}
          className="flex items-center gap-1 text-muted hover:text-slate-300 text-sm transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        <div className="flex-1" />
        <div className="text-xs text-muted font-mono">Guided · Q{questionNumber}/10</div>
      </div>

      <div className="bg-card border border-border rounded-2xl p-6">
        {!question ? (
          <div className="flex items-center gap-2 text-muted">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm">Preparing your first question…</span>
          </div>
        ) : (
          <>
            <div className="text-slate-200 text-sm leading-relaxed whitespace-pre-wrap">
              {question.text}
            </div>

            <div className="mt-5">
              {isSingle && (
                <select
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  disabled={submitting}
                  className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-all"
                >
                  <option value="" disabled>
                    Select one…
                  </option>
                  {options.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              )}

              {isMulti && (
                <div className="space-y-2">
                  {options.map((o) => (
                    <label key={o} className="flex items-center gap-2 text-sm text-slate-200">
                      <input
                        type="checkbox"
                        checked={multi.includes(o)}
                        onChange={() => toggleMulti(o)}
                        disabled={submitting}
                      />
                      <span>{o}</span>
                    </label>
                  ))}
                </div>
              )}

              {(isText || isNumber) && (
                <input
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  type="text"
                  inputMode={isNumber ? 'numeric' : 'text'}
                  placeholder={isNumber ? 'e.g. 200' : 'Type your answer…'}
                  disabled={submitting}
                  className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-muted focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-all"
                />
              )}
            </div>

            <div className="mt-5 flex justify-end">
              <button
                onClick={submit}
                disabled={!canSubmit || submitting}
                className="px-5 py-2.5 rounded-xl bg-primary hover:bg-primary-hover disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm transition-all"
              >
                {submitting ? 'Submitting…' : 'Next'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

