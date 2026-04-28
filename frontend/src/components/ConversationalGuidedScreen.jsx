import { useState, useEffect, useRef } from 'react'
import { ArrowLeft, Send, Loader2, MessageSquare, Pencil } from 'lucide-react'
import { api } from '../api/client'
import useStore from '../store/useStore'
import LoadingSpinner from './shared/LoadingSpinner'

export default function ConversationalGuidedScreen() {
  const {
    userInput, scopeResult,
    setSolution, setAnalysisBlocks, setScreen, setLoading, setError, loading,
  } = useStore()

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [followup, setFollowup] = useState({ active: false, answers: {}, question: null })
  const [editingKey, setEditingKey] = useState(null)
  const [editingValue, setEditingValue] = useState('')
  const [editingMsgIdx, setEditingMsgIdx] = useState(null) // index into messages
  const [editingMsgText, setEditingMsgText] = useState('')
  const bottomRef = useRef(null)

  // Kick off conversation immediately on mount
  useEffect(() => {
    startConversation()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const startConversation = async () => {
    setSending(true)
    try {
      const res = await api.conversationalMessage(userInput, scopeResult, [], '', 5, null)
      if (res?.session_id) setSessionId(res.session_id)
      if (res.message) {
        setMessages([{ role: 'assistant', content: res.message }])
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  const continueFromHistory = async (historyMessages) => {
    setSending(true)
    setError(null)
    try {
      const res = await api.conversationalMessage(
        userInput,
        scopeResult,
        historyMessages.map((m) => ({ role: m.role, content: m.content })),
        '',
        5,
        null,
      )
      if (res?.session_id) setSessionId(res.session_id)
      if (res?.message) {
        setMessages([...historyMessages, { role: 'assistant', content: res.message }])
      } else {
        setMessages(historyMessages)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  const applyEdit = async () => {
    if (!followup.active || !editingKey) return
    const nextAnswers = { ...(followup.answers || {}), [editingKey]: editingValue }
    setFollowup((prev) => ({ ...prev, answers: nextAnswers }))
    setEditingKey(null)
    setEditingValue('')
    // No re-review here. Review is single-shot; edits just update stored answers.
  }

  const applyMessageEdit = async () => {
    if (editingMsgIdx === null || editingMsgIdx === undefined) return
    const idx = Number(editingMsgIdx)
    if (!Number.isFinite(idx) || idx < 0 || idx >= messages.length) return
    const edited = editingMsgText.trim()
    if (!edited) return

    const newHistory = messages.slice(0, idx + 1).map((m, i) =>
      i === idx ? { ...m, content: edited } : m,
    )

    // Reset follow-up mode because the conversation history changed.
    setFollowup({ active: false, answers: {}, question: null })
    setSessionId(null)
    setEditingMsgIdx(null)
    setEditingMsgText('')
    await continueFromHistory(newHistory)
  }

  const skipMainOrFollowup = async () => {
    if (sending) return

    // If we're in follow-up, reuse the existing skip behavior.
    if (followup.active) {
      await skipFollowup()
      return
    }

    setInput('')
    const newMessages = [...messages, { role: 'user', content: '(skip)' }]
    setMessages(newMessages)
    setSending(true)
    setError(null)
    try {
      const res = await api.conversationalMessage(
        userInput,
        scopeResult,
        messages.map((m) => ({ role: m.role, content: m.content })),
        '(skip)',
        5,
        sessionId,
      )
      if (res?.session_id) setSessionId(res.session_id)
      if (res.is_complete && res.collected_answers) {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: "Thanks — quick sanity check so I don’t make wrong assumptions…" },
        ])
        const review = await api.conversationalReview(userInput, scopeResult, res.collected_answers)
        if (review.status === 'complete') {
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: "Perfect. Generating your architecture…" },
          ])
          setGenerating(true)
          setSending(false)
          const solution = await api.smartGuidedComplete(userInput, scopeResult, res.collected_answers)
          setSolution(solution)
          if (solution.analysis_blocks) setAnalysisBlocks(solution.analysis_blocks)
          setScreen('solution')
          return
        }
        const q = review.question
        setFollowup({ active: true, answers: res.collected_answers, question: q })
        if (q?.text) {
          setMessages((prev) => [...prev, { role: 'assistant', content: q.text }])
        }
        setSending(false)
      } else if (res.message) {
        setMessages((prev) => [...prev, { role: 'assistant', content: res.message }])
        setSending(false)
      }
    } catch (err) {
      setError(err.message)
      setSending(false)
    }
  }

  const skipFollowup = async () => {
    if (!followup.active || !followup.question?.field || sending) return
    // Mark as intentionally skipped and proceed to architecture (single-shot review).
    const nextAnswers = { ...(followup.answers || {}), [followup.question.field]: '__skipped__' }
    setMessages((prev) => [...prev, { role: 'user', content: '(skip)' }])
    try {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: "Got it. Generating your architecture with best‑guess defaults for the skipped detail…" },
      ])
      setGenerating(true)
      const solution = await api.smartGuidedComplete(userInput, scopeResult, nextAnswers)
      setSolution(solution)
      if (solution.analysis_blocks) setAnalysisBlocks(solution.analysis_blocks)
      setScreen('solution')
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  const sendMessage = async () => {
    const trimmed = input.trim()
    if (!trimmed || sending) return

    const newMessages = [...messages, { role: 'user', content: trimmed }]
    setMessages(newMessages)
    setInput('')
    setSending(true)
    setError(null)

    try {
      // Follow-up mode: answer targeted questions until blocks look good.
      if (followup.active) {
        const q = followup.question
        const field = q?.field
        const nextAnswers = { ...(followup.answers || {}) }
        if (field) nextAnswers[field] = trimmed
        // Single-shot clarification: after answering, proceed to architecture (no further review loop).
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: "Perfect — generating your architecture…" },
        ])
        setGenerating(true)
        setSending(false)
        const solution = await api.smartGuidedComplete(userInput, scopeResult, nextAnswers)
        setSolution(solution)
        if (solution.analysis_blocks) setAnalysisBlocks(solution.analysis_blocks)
        setScreen('solution')
        return
      }

      const res = await api.conversationalMessage(
        userInput,
        scopeResult,
        // pass all except the last user message as history
        messages.map((m) => ({ role: m.role, content: m.content })),
        trimmed,
        5,
        sessionId,
      )
      if (res?.session_id) setSessionId(res.session_id)

      if (res.is_complete && res.collected_answers) {
        // Run analysis in the background (server-side) and ask follow-ups only if needed.
        setMessages((prev) => {
          const out = [...prev]
          if (res.message) out.push({ role: 'assistant', content: res.message })
          return out
        })
        const review = await api.conversationalReview(userInput, scopeResult, res.collected_answers)
        if (review.status === 'complete') {
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: "Perfect. Generating your architecture…" },
          ])
          setGenerating(true)
          setSending(false)
          const solution = await api.smartGuidedComplete(userInput, scopeResult, res.collected_answers)
          setSolution(solution)
          if (solution.analysis_blocks) setAnalysisBlocks(solution.analysis_blocks)
          setScreen('solution')
          return
        }

        const q = review.question
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: "Thanks — quick sanity check so I don’t make wrong assumptions…" },
        ])
        setFollowup({ active: true, answers: res.collected_answers, question: q })
        if (q?.text) {
          setMessages((prev) => [...prev, { role: 'assistant', content: q.text }])
        }
        setSending(false)
      } else if (res.message) {
        setMessages((prev) => [...prev, { role: 'assistant', content: res.message }])
        setSending(false)
      }
    } catch (err) {
      setError(err.message)
      setSending(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  if (generating || loading) {
    return (
      <div className="flex flex-col items-center pt-16">
        <LoadingSpinner message="Building your cloud architecture…" size="lg" />
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-4 max-w-5xl mx-auto animate-slide-up">
      <div className="flex flex-col h-[calc(100vh-10rem)]">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4 shrink-0">
        <button
          onClick={() => setScreen('mode-selection')}
          className="flex items-center gap-1 text-muted hover:text-slate-300 text-sm transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        <div className="flex-1" />
        <div className="flex items-center gap-2 text-primary-light">
          <MessageSquare className="w-4 h-4" />
          <span className="text-sm font-medium">Guided Mode</span>
        </div>
      </div>

      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1 min-h-0">
        {sending && messages.length === 0 ? (
          <div className="flex justify-start">
            <div className="bg-card border border-border rounded-2xl rounded-tl-sm px-4 py-3 max-w-[80%]">
              <Loader2 className="w-4 h-4 animate-spin text-primary" />
            </div>
          </div>
        ) : (
          messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`px-4 py-3 rounded-2xl text-sm leading-relaxed max-w-[80%] whitespace-pre-wrap ${
                  m.role === 'user'
                    ? 'bg-primary/20 border border-primary/30 text-slate-200 rounded-tr-sm'
                    : 'bg-card border border-border text-slate-300 rounded-tl-sm'
                }`}
              >
                <div className="flex items-start gap-2">
                  <div className="flex-1">{m.content}</div>
                  {m.role === 'user' && !sending && (
                    <button
                      onClick={() => {
                        setEditingMsgIdx(i)
                        setEditingMsgText(m.content)
                      }}
                      className="p-1 rounded-lg hover:bg-surface/60 text-muted hover:text-slate-200"
                      title="Edit this answer"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
        {sending && messages.length > 0 && (
          <div className="flex justify-start">
            <div className="bg-card border border-border rounded-2xl rounded-tl-sm px-4 py-3">
              <Loader2 className="w-4 h-4 animate-spin text-primary" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="mt-4 shrink-0">
        {editingMsgIdx !== null && (
          <div className="mb-3 bg-card border border-border rounded-2xl p-3">
            <div className="text-xs text-muted mb-2">Editing a previous answer</div>
            <textarea
              value={editingMsgText}
              onChange={(e) => setEditingMsgText(e.target.value)}
              rows={2}
              className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-slate-200 placeholder-muted resize-none focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-all"
            />
            <div className="mt-2 flex justify-end gap-2">
              <button
                onClick={() => {
                  setEditingMsgIdx(null)
                  setEditingMsgText('')
                }}
                className="px-3 py-1.5 rounded-xl border border-border text-xs text-slate-200 hover:bg-surface/60"
              >
                Cancel
              </button>
              <button
                onClick={applyMessageEdit}
                disabled={sending}
                className="px-3 py-1.5 rounded-xl bg-primary hover:bg-primary-hover disabled:opacity-40 text-xs text-white"
              >
                Apply edit
              </button>
            </div>
          </div>
        )}
        <div className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Type your answer…"
            rows={2}
            disabled={sending}
            className="flex-1 bg-card border border-border rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-muted resize-none focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-all disabled:opacity-50"
          />
          <button
            onClick={skipMainOrFollowup}
            disabled={sending}
            className="px-3 py-3 rounded-xl border border-border text-xs text-slate-200 hover:bg-surface/60 disabled:opacity-40 disabled:cursor-not-allowed transition-all self-end"
            title="Skip this question"
          >
            Skip
          </button>
          <button
            onClick={sendMessage}
            disabled={!input.trim() || sending}
            className="p-3 rounded-xl bg-primary hover:bg-primary-hover disabled:opacity-40 disabled:cursor-not-allowed text-white transition-all self-end"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-muted mt-1.5 text-center">Press Enter to send · Shift+Enter for new line</p>
      </div>
      </div>

      {/* Captured answers (editable) – only during follow-up/review */}
      <div className="hidden lg:block">
        <div className="bg-card border border-border rounded-2xl p-4">
          <div className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Captured answers</div>
          {!followup.active ? (
            <div className="text-xs text-muted">Answers will appear here after the initial chat completes.</div>
          ) : (
            <div className="space-y-2">
              {Object.entries(followup.answers || {}).map(([k, v]) => (
                <div key={k} className="border border-border rounded-xl p-2">
                  <div className="text-[11px] text-muted break-words">{k}</div>
                  <div className="mt-1 flex items-center gap-2">
                    <div className="text-xs text-slate-200 break-words flex-1">
                      {String(v)}
                    </div>
                    <button
                      onClick={() => {
                        setEditingKey(k)
                        setEditingValue(String(v ?? ''))
                      }}
                      className="p-1 rounded-lg hover:bg-surface/60 text-muted hover:text-slate-200"
                      title="Edit"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
              {editingKey && (
                <div className="mt-3 border-t border-border pt-3">
                  <div className="text-[11px] text-muted mb-1">Edit</div>
                  <div className="text-[11px] text-muted break-words">{editingKey}</div>
                  <input
                    value={editingValue}
                    onChange={(e) => setEditingValue(e.target.value)}
                    className="mt-2 w-full bg-surface border border-border rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-all"
                  />
                  <div className="mt-2 flex gap-2 justify-end">
                    <button
                      onClick={() => {
                        setEditingKey(null)
                        setEditingValue('')
                      }}
                      className="px-3 py-1.5 rounded-xl border border-border text-xs text-slate-200 hover:bg-surface/60"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={applyEdit}
                      disabled={sending}
                      className="px-3 py-1.5 rounded-xl bg-primary hover:bg-primary-hover disabled:opacity-40 text-xs text-white"
                    >
                      Apply
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
