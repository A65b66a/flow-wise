import { useState, useEffect, useRef } from 'react'
import {
  ArrowLeft, Terminal, Cpu, AlertTriangle, Send,
  CheckCircle2, Circle, ChevronDown, ChevronUp,
} from 'lucide-react'
import { api } from '../api/client'
import useStore from '../store/useStore'
import { validateCloudAnswer } from '../utils/cloudValidation'

const BLOCK_LABELS = ['App Identity', 'Architecture', 'Network', 'Scale', 'Availability', 'Security', 'Budget']
const BLOCK_KEYS = [
  'analysis_block_1_application_identity',
  'analysis_block_2_architecture_pattern',
  'analysis_block_3_network_design',
  'analysis_block_4_traffic_and_scale',
  'analysis_block_5_availability',
  'analysis_block_6_access_and_security',
  'analysis_block_7_resource_sizing_and_budget',
]

function blockFillStatus(blocks) {
  return BLOCK_KEYS.map((key) => {
    const b = blocks[key]
    if (!b) return 'empty'
    const nonEmpty = Object.values(b).filter(
      (v) => v !== null && v !== undefined && v !== '' && v !== 'null',
    )
    return nonEmpty.length > 0 ? 'filled' : 'empty'
  })
}

export default function ExpertModeScreen() {
  const {
    userInput, scopeResult,
    setExpertRound,
    addExpertTurn,
    setExpertAnalysisBlocks,
    setExpertIsComplete,
    setExpertBlocksFilled,
    setSolution, setScreen, setLoading, setError,
  } = useStore()

  // ── chat state ─────────────────────────────────────────────────────────
  const [messages, setMessages] = useState([])
  const [currentQ, setCurrentQ] = useState(null)
  const [queuedQs, setQueuedQs] = useState([])
  const [roundAnswers, setRoundAnswers] = useState({})

  const [textInput, setTextInput] = useState('')
  const [multiSel, setMultiSel] = useState([])
  const [inputError, setInputError] = useState(null)
  const [isThinking, setIsThinking] = useState(false)
  const [isDone, setIsDone] = useState(false)
  const [qSource, setQSource] = useState('llm')
  const [showBlocks, setShowBlocks] = useState(false)
  const [localBlocks, setLocalBlocks] = useState({})

  // refs so event-handler closures always see the latest values
  const blocksRef = useRef({})
  const historyRef = useRef([])
  const roundRef = useRef(1)
  const roundAllQsRef = useRef([])

  const messagesEndRef = useRef(null)
  const textInputRef = useRef(null)

  // ── auto-scroll ─────────────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking])

  // ── auto-focus text input ───────────────────────────────────────────────
  useEffect(() => {
    if (currentQ?.type === 'text' || currentQ?.type === 'number') {
      textInputRef.current?.focus()
    }
  }, [currentQ])

  // ── kick off on mount ───────────────────────────────────────────────────
  useEffect(() => {
    fetchRound(1, [], {})
  }, [])

  // ── helpers ─────────────────────────────────────────────────────────────
  const pushMsg = (msg) =>
    setMessages((prev) => [...prev, { _id: Math.random(), ...msg }])

  const showNextQuestion = (question) => {
    pushMsg({
      role: 'ai',
      content: question.text,
      why: question.why,
      blockRef: question.block_ref,
    })
    setCurrentQ(question)
  }

  // ── fetch a round from the backend ─────────────────────────────────────
  const fetchRound = async (round, history, blocks) => {
    setIsThinking(true)
    setCurrentQ(null)
    try {
      const data = await api.expertQuestions(
        userInput, scopeResult, round, history, blocks,
      )
      const newBlocks = data.analysis_blocks || blocks
      const questions = data.questions || []

      // keep refs in sync
      blocksRef.current = newBlocks
      historyRef.current = history
      roundRef.current = data.round
      roundAllQsRef.current = questions

      // update store / display state
      setExpertRound(data.round)
      setExpertAnalysisBlocks(newBlocks)
      setExpertBlocksFilled(data.blocks_filled_count || 0)
      setLocalBlocks(newBlocks)
      setQSource(data.source || 'llm')

      setIsThinking(false)

      if (data.is_complete) {
        setIsDone(true)
        setExpertIsComplete(true)
        pushMsg({
          role: 'ai',
          content:
            "I now have all the information needed to generate your cloud architecture. All critical specification blocks are filled. Click **Generate Architecture** when you're ready.",
          isComplete: true,
        })
        return
      }

      // intro message
      if (round === 1) {
        pushMsg({
          role: 'ai',
          content:
            "Hello! I'm your Expert Cloud Architect. I'll ask you targeted questions to build a complete infrastructure specification. Let's begin.",
        })
      } else {
        pushMsg({
          role: 'ai',
          content: `Thanks. I need a few more details to complete your specification.`,
        })
      }

      setRoundAnswers({})
      setTextInput('')
      setMultiSel([])

      if (questions.length > 0) {
        const [first, ...rest] = questions
        setQueuedQs(rest)
        showNextQuestion(first)
      }
    } catch (err) {
      setIsThinking(false)
      setError(err.message)
    }
  }

  // ── user submits an answer ──────────────────────────────────────────────
  const submitAnswer = (answer) => {
    if (!currentQ) return

    // validate free-text answers
    if (currentQ.type === 'text') {
      const err = validateCloudAnswer(String(answer))
      if (err) { setInputError(err); return }
    }
    setInputError(null)

    // show user bubble
    const display = Array.isArray(answer) ? answer.join(', ') : String(answer)
    pushMsg({ role: 'user', content: display })

    const newAnswers = { ...roundAnswers, [currentQ.id]: answer }
    setRoundAnswers(newAnswers)
    setTextInput('')
    setMultiSel([])
    setCurrentQ(null)

    if (queuedQs.length > 0) {
      // next question in this round
      const [next, ...rest] = queuedQs
      setQueuedQs(rest)
      showNextQuestion(next)
    } else {
      // round complete — build history entry and fetch next round
      const qaPairs = roundAllQsRef.current.map((q) => ({
        question: q.text,
        answer: newAnswers[q.id] ?? '',
      }))
      const newTurn = { round: roundRef.current, qa_pairs: qaPairs }
      addExpertTurn(newTurn)
      const newHistory = [...historyRef.current, newTurn]
      historyRef.current = newHistory
      fetchRound(roundRef.current + 1, newHistory, blocksRef.current)
    }
  }

  const handleGenerate = async () => {
    setLoading(true)
    setError(null)
    try {
      const solution = await api.expertComplete(userInput, scopeResult, blocksRef.current)
      setSolution(solution)
      setScreen('solution')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const fillStatus = blockFillStatus(localBlocks)
  const filledCount = fillStatus.filter((s) => s === 'filled').length

  return (
    <div className="flex flex-col max-w-2xl mx-auto" style={{ height: 'calc(100vh - 110px)' }}>

      {/* ── top bar ──────────────────────────────────────────────────────── */}
      <div className="flex-shrink-0 space-y-2 pb-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setScreen('mode-selection')}
            className="flex items-center gap-1 text-muted hover:text-slate-300 text-sm transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Back
          </button>
          <div className="flex-1" />
          {qSource === 'llm' ? (
            <span className="flex items-center gap-1 text-[10px] text-green-400/80 bg-green-900/20 border border-green-800/40 px-2 py-0.5 rounded-full">
              <Cpu className="w-2.5 h-2.5" /> AI-generated
            </span>
          ) : (
            <span className="flex items-center gap-1 text-[10px] text-amber-400/80 bg-amber-900/20 border border-amber-700/40 px-2 py-0.5 rounded-full">
              <AlertTriangle className="w-2.5 h-2.5" /> Default questions
            </span>
          )}
          <div className="flex items-center gap-1.5 text-yellow-400">
            <Terminal className="w-4 h-4" />
            <span className="text-sm font-medium">Expert Mode</span>
          </div>
        </div>

        {/* collapsible block-fill strip */}
        <button
          onClick={() => setShowBlocks(!showBlocks)}
          className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-card border border-border text-xs text-muted hover:text-slate-300 transition-colors"
        >
          <span className="font-semibold uppercase tracking-wider">
            Spec blocks — {filledCount}/7 filled
          </span>
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {fillStatus.map((s, i) => (
                <div
                  key={i}
                  title={BLOCK_LABELS[i]}
                  className={`w-2 h-2 rounded-full transition-colors ${s === 'filled' ? 'bg-yellow-400' : 'bg-border'}`}
                />
              ))}
            </div>
            {showBlocks ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </div>
        </button>

        {showBlocks && (
          <div className="flex flex-wrap gap-1.5 px-1 pb-1">
            {BLOCK_LABELS.map((label, i) => (
              <div
                key={label}
                className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs border transition-all ${
                  fillStatus[i] === 'filled'
                    ? 'bg-yellow-900/20 border-yellow-600/40 text-yellow-300'
                    : 'bg-surface border-border text-muted'
                }`}
              >
                {fillStatus[i] === 'filled'
                  ? <CheckCircle2 className="w-3 h-3 text-yellow-400" />
                  : <Circle className="w-3 h-3" />}
                {label}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── chat messages ─────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto space-y-4 py-2 pr-1 min-h-0">
        {messages.map((msg) =>
          msg.role === 'ai' ? (
            <AiMessage key={msg._id} msg={msg} onGenerate={msg.isComplete ? handleGenerate : null} />
          ) : (
            <UserMessage key={msg._id} content={msg.content} />
          ),
        )}

        {isThinking && <TypingIndicator />}
        <div ref={messagesEndRef} />
      </div>

      {/* ── input area ───────────────────────────────────────────────────── */}
      <div className="flex-shrink-0 pt-3 border-t border-border">
        {isDone ? (
          <button
            onClick={handleGenerate}
            className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-yellow-600 hover:bg-yellow-500 text-white font-semibold text-sm transition-all shadow-lg shadow-yellow-900/30"
          >
            Generate Architecture →
          </button>
        ) : currentQ && !isThinking ? (
          <AnswerInput
            question={currentQ}
            textInput={textInput}
            setTextInput={setTextInput}
            multiSel={multiSel}
            setMultiSel={setMultiSel}
            inputError={inputError}
            setInputError={setInputError}
            onSubmit={submitAnswer}
            textInputRef={textInputRef}
          />
        ) : !isThinking ? (
          <div className="py-2 text-center text-xs text-muted">Waiting for next question…</div>
        ) : null}
      </div>
    </div>
  )
}

// ── AI message bubble ───────────────────────────────────────────────────────
function AiMessage({ msg, onGenerate }) {
  return (
    <div className="flex items-start gap-3">
      <div className="w-8 h-8 rounded-lg bg-yellow-900/40 border border-yellow-600/40 flex items-center justify-center shrink-0 mt-0.5">
        <Terminal className="w-4 h-4 text-yellow-400" />
      </div>
      <div className="flex-1 space-y-1 max-w-[85%]">
        {msg.blockRef && (
          <span className="text-[10px] font-mono text-yellow-500/50 pl-0.5">
            {msg.blockRef.replace('analysis_block_', 'Block ').replace(/_[a-z_]+$/, '')}
          </span>
        )}
        <div className="bg-card border border-border rounded-2xl rounded-tl-none px-4 py-3 text-sm text-slate-200 leading-relaxed">
          {msg.content}
        </div>
        {msg.why && (
          <p className="text-xs text-muted pl-1 flex items-start gap-1">
            <span className="text-yellow-500 shrink-0 mt-0.5">→</span>
            {msg.why}
          </p>
        )}
        {onGenerate && (
          <button
            onClick={onGenerate}
            className="mt-2 ml-0.5 flex items-center gap-2 px-4 py-2 rounded-xl bg-yellow-600 hover:bg-yellow-500 text-white font-semibold text-sm transition-all shadow-md shadow-yellow-900/30"
          >
            Generate Architecture →
          </button>
        )}
      </div>
    </div>
  )
}

// ── User message bubble ─────────────────────────────────────────────────────
function UserMessage({ content }) {
  return (
    <div className="flex justify-end">
      <div className="bg-primary/20 border border-primary/30 rounded-2xl rounded-tr-none px-4 py-2.5 text-sm text-slate-200 max-w-[75%] leading-relaxed">
        {content}
      </div>
    </div>
  )
}

// ── Typing indicator ────────────────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div className="flex items-start gap-3">
      <div className="w-8 h-8 rounded-lg bg-yellow-900/40 border border-yellow-600/40 flex items-center justify-center shrink-0">
        <Terminal className="w-4 h-4 text-yellow-400" />
      </div>
      <div className="bg-card border border-border rounded-2xl rounded-tl-none px-4 py-3.5">
        <div className="flex gap-1.5 items-center">
          {[0, 150, 300].map((delay) => (
            <span
              key={delay}
              className="w-1.5 h-1.5 rounded-full bg-yellow-400/70 animate-bounce"
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Answer input — changes shape based on question type ─────────────────────
function AnswerInput({
  question, textInput, setTextInput,
  multiSel, setMultiSel,
  inputError, setInputError,
  onSubmit, textInputRef,
}) {
  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (textInput.trim()) onSubmit(textInput.trim())
    }
  }

  if (question.type === 'text' || question.type === 'number') {
    return (
      <div className="space-y-2">
        {inputError && (
          <p className="flex items-start gap-1.5 text-xs text-red-400 px-1">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            {inputError}
          </p>
        )}
        <div className="flex gap-2">
          <input
            ref={textInputRef}
            type={question.type === 'number' ? 'number' : 'text'}
            value={textInput}
            onChange={(e) => {
              setTextInput(e.target.value)
              if (inputError) setInputError(null)
            }}
            onKeyDown={handleKey}
            placeholder={question.placeholder || 'Type your answer…'}
            className={`flex-1 bg-surface border rounded-xl px-4 py-2.5 text-sm text-slate-200 placeholder-muted focus:outline-none transition-all font-mono ${
              inputError
                ? 'border-red-500/60 focus:border-red-500 focus:ring-1 focus:ring-red-500/30'
                : 'border-border focus:border-yellow-600/60 focus:ring-1 focus:ring-yellow-600/30'
            }`}
          />
          <button
            onClick={() => { if (textInput.trim()) onSubmit(textInput.trim()) }}
            disabled={!textInput.trim()}
            className="px-3 py-2.5 rounded-xl bg-yellow-600 hover:bg-yellow-500 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-all"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    )
  }

  if (question.type === 'select') {
    return (
      <div className="flex flex-wrap gap-2">
        {question.options?.map((opt) => (
          <button
            key={opt}
            onClick={() => onSubmit(opt)}
            className="px-3 py-2 rounded-xl border border-border bg-surface text-sm font-mono text-subtle hover:border-yellow-600/60 hover:text-yellow-300 hover:bg-yellow-900/20 transition-all"
          >
            {opt}
          </button>
        ))}
      </div>
    )
  }

  if (question.type === 'multiselect') {
    return (
      <div className="space-y-2">
        <div className="flex flex-wrap gap-2">
          {question.options?.map((opt) => {
            const sel = multiSel.includes(opt)
            return (
              <button
                key={opt}
                onClick={() =>
                  setMultiSel(sel ? multiSel.filter((x) => x !== opt) : [...multiSel, opt])
                }
                className={`px-3 py-2 rounded-xl border text-sm font-mono transition-all ${
                  sel
                    ? 'bg-yellow-900/30 border-yellow-500/60 text-yellow-300'
                    : 'border-border bg-surface text-subtle hover:border-yellow-600/40 hover:text-slate-300'
                }`}
              >
                {opt}
              </button>
            )
          })}
        </div>
        <button
          onClick={() => onSubmit(multiSel)}
          disabled={multiSel.length === 0}
          className="w-full py-2.5 rounded-xl bg-yellow-600 hover:bg-yellow-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold text-sm transition-all"
        >
          Confirm →
        </button>
      </div>
    )
  }

  if (question.type === 'boolean') {
    return (
      <div className="flex gap-2">
        {['Yes', 'No'].map((opt) => (
          <button
            key={opt}
            onClick={() => onSubmit(opt === 'Yes')}
            className="flex-1 py-2.5 rounded-xl border border-border bg-surface text-sm font-medium text-subtle hover:border-yellow-600/60 hover:text-yellow-300 hover:bg-yellow-900/20 transition-all"
          >
            {opt}
          </button>
        ))}
      </div>
    )
  }

  return null
}
