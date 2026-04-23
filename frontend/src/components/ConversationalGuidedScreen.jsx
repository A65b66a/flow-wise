import { useState, useEffect, useRef } from 'react'
import { ArrowLeft, Send, Loader2, MessageSquare } from 'lucide-react'
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
      const res = await api.conversationalMessage(userInput, scopeResult, [], '')
      if (res.message) {
        setMessages([{ role: 'assistant', content: res.message }])
      }
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
      const res = await api.conversationalMessage(
        userInput,
        scopeResult,
        // pass all except the last user message as history
        messages.map((m) => ({ role: m.role, content: m.content })),
        trimmed,
      )

      if (res.is_complete && res.collected_answers) {
        // LLM has enough info — generate architecture
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: "Perfect, I have everything I need. Generating your architecture…" },
        ])
        setGenerating(true)
        setSending(false)
        const solution = await api.smartGuidedComplete(userInput, scopeResult, res.collected_answers)
        setSolution(solution)
        if (solution.analysis_blocks) setAnalysisBlocks(solution.analysis_blocks)
        setScreen('solution')
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
                {m.content}
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
  )
}
