import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Loader2, Send, MessageSquare } from 'lucide-react'
import { api } from '../api/client'
import useStore from '../store/useStore'
import LoadingSpinner from './shared/LoadingSpinner'

const MIN_EXPERT_QUESTIONS = 20

// Expert Mode UI is intentionally not field-aware.
// The backend/LLM controls progression and extraction.

export default function ExpertModeScreen() {
  const { userInput, scopeResult, setSolution, setAnalysisBlocks, setScreen, setError, loading } = useStore()

  const [sessionId, setSessionId] = useState(null)
  const [question, setQuestion] = useState(null)
  const [questionNumber, setQuestionNumber] = useState(1)

  const [value, setValue] = useState('')

  const [messages, setMessages] = useState([])
  const [sending, setSending] = useState(false)
  const [generating, setGenerating] = useState(false)

  const bottomRef = useRef(null)

  const q = question

  const canSubmit = useMemo(() => {
    if (!q || sending) return false
    return String(value || '').trim().length > 0
  }, [q, sending, value])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    const start = async () => {
      setSending(true)
      setError(null)
      try {
        const res = await api.expertLoopStart(userInput, scopeResult, MIN_EXPERT_QUESTIONS, 30)
        setSessionId(res.session_id)
        if (res.status === 'complete') {
          if (res.analysis_blocks) setAnalysisBlocks(res.analysis_blocks)
          const session = await api.expertLoopSession(res.session_id)
          const solution = await api.smartGuidedComplete(userInput, scopeResult, session.answers || {})
          setSolution(solution)
          if (solution.analysis_blocks) setAnalysisBlocks(solution.analysis_blocks)
          setScreen('solution')
          return
        }
        setQuestion(res.question)
        setQuestionNumber(res.question_number || 1)
        if (res.question?.text) setMessages([{ role: 'assistant', content: res.question.text }])
        setValue('')
      } catch (err) {
        setError(err.message)
      } finally {
        setSending(false)
      }
    }
    start()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    // Reset input when question changes.
    setValue('')
  }, [questionNumber])

  const submit = async (skip = false) => {
    if (!q) return
    if (sending || !sessionId) return

    setSending(true)
    setError(null)

    const userText = skip ? '(skip)' : String(value || '').trim()
    setMessages((prev) => [...prev, { role: 'user', content: userText || '(skip)' }])

    try {
      const res = await api.expertLoopAnswer(sessionId, q.field, userText || '(skip)')
      if (res.status === 'complete') {
        setMessages((prev) => [...prev, { role: 'assistant', content: 'Got it. Generating your architecture…' }])
        setGenerating(true)
        if (res.analysis_blocks) setAnalysisBlocks(res.analysis_blocks)
        const session = await api.expertLoopSession(res.session_id)
        const solution = await api.smartGuidedComplete(userInput, scopeResult, session.answers || {})
        setSolution(solution)
        if (solution.analysis_blocks) setAnalysisBlocks(solution.analysis_blocks)
        setScreen('solution')
        return
      }
      setQuestion(res.question)
      setQuestionNumber(res.question_number || (questionNumber + 1))
      setValue('')
      if (res.question?.text) setMessages((prev) => [...prev, { role: 'assistant', content: res.question.text }])
    } catch (err) {
      setError(err.message)
    } finally {
      setGenerating(false)
      setSending(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit(false)
    }
  }

  if (generating || loading) {
    return (
      <div className="flex flex-col items-center pt-16">
        <LoadingSpinner message="Building your cloud architecture…" size="lg" />
      </div>
    )
  }

  if (!q) return null

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] max-w-2xl mx-auto animate-slide-up">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4 shrink-0">
        <button
          onClick={() => setScreen('mode-selection')}
          className="flex items-center gap-1 text-muted hover:text-slate-300 text-sm transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        <div className="flex-1" />
        <div className="flex items-center gap-2 text-yellow-300">
          <MessageSquare className="w-4 h-4" />
          <span className="text-sm font-medium">Expert Mode · Q{questionNumber}{questionNumber < MIN_EXPERT_QUESTIONS ? `/${MIN_EXPERT_QUESTIONS}+` : ''}</span>
        </div>
      </div>

      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1 min-h-0">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`px-4 py-3 rounded-2xl text-sm leading-relaxed max-w-[80%] whitespace-pre-wrap ${
                m.role === 'user'
                  ? 'bg-yellow-900/20 border border-yellow-500/20 text-slate-200 rounded-tr-sm'
                  : 'bg-card border border-border text-slate-300 rounded-tl-sm'
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {sending && (
          <div className="flex justify-start">
            <div className="bg-card border border-border rounded-2xl rounded-tl-sm px-4 py-3">
              <Loader2 className="w-4 h-4 animate-spin text-yellow-300" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="mt-4 shrink-0">
        <div className="flex gap-2 items-end">
          <textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Type your answer…"
            rows={2}
            disabled={sending}
            className="flex-1 bg-card border border-border rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-muted resize-none focus:outline-none focus:border-yellow-400/60 focus:ring-1 focus:ring-yellow-400/30 transition-all disabled:opacity-50"
          />
          <button
            onClick={() => submit(true)}
            disabled={sending}
            className="px-3 py-3 rounded-xl border border-border text-xs text-slate-200 hover:bg-surface/60 disabled:opacity-40 disabled:cursor-not-allowed transition-all self-end"
            title="Skip this question"
          >
            Skip
          </button>
          <button
            onClick={() => submit(false)}
            disabled={!canSubmit}
            className="p-3 rounded-xl bg-yellow-500 hover:bg-yellow-400 disabled:opacity-40 disabled:cursor-not-allowed text-black transition-all self-end"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-muted mt-1.5 text-center">
          Press Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  )
}

