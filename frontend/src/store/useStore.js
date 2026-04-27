import { create } from 'zustand'

const useStore = create((set) => ({
  screen: 'entry',
  setScreen: (screen) => set({ screen }),

  userInput: '',
  setUserInput: (userInput) => set({ userInput }),

  scopeResult: null,
  setScopeResult: (scopeResult) => set({ scopeResult }),

  modeResult: null,
  setModeResult: (modeResult) => set({ modeResult }),

  selectedMode: null,
  setSelectedMode: (selectedMode) => set({ selectedMode }),

  autoPilotInit: null,
  setAutoPilotInit: (autoPilotInit) => set({ autoPilotInit }),

  quickInputs: { users: '', visibility: 'public', uptime: '99.9%' },
  setQuickInputs: (quickInputs) => set({ quickInputs }),

  currentBlock: 1,
  setCurrentBlock: (currentBlock) => set({ currentBlock }),

  guidedQuestions: {},
  setGuidedQuestions: (block, questions) =>
    set((s) => ({ guidedQuestions: { ...s.guidedQuestions, [block]: questions } })),

  guidedAnswers: {},
  setBlockAnswers: (block, answers) =>
    set((s) => ({ guidedAnswers: { ...s.guidedAnswers, [`block_${block}`]: answers } })),

  expertRound: 1,
  setExpertRound: (expertRound) => set({ expertRound }),

  expertQuestions: [],
  setExpertQuestions: (expertQuestions) => set({ expertQuestions }),

  expertConversationHistory: [],
  addExpertTurn: (turn) =>
    set((s) => ({ expertConversationHistory: [...s.expertConversationHistory, turn] })),

  expertAnalysisBlocks: {},
  setExpertAnalysisBlocks: (expertAnalysisBlocks) => set({ expertAnalysisBlocks }),

  expertIsComplete: false,
  setExpertIsComplete: (expertIsComplete) => set({ expertIsComplete }),

  expertBlocksFilled: 0,
  setExpertBlocksFilled: (expertBlocksFilled) => set({ expertBlocksFilled }),

  solution: null,
  setSolution: (solution) => set({ solution }),

  loading: false,
  setLoading: (loading) => set({ loading }),

  error: null,
  setError: (error) => set({ error }),

  reset: () =>
    set({
      screen: 'entry',
      userInput: '',
      scopeResult: null,
      modeResult: null,
      selectedMode: null,
      autoPilotInit: null,
      quickInputs: { users: '', visibility: 'public', uptime: '99.9%' },
      currentBlock: 1,
      guidedQuestions: {},
      guidedAnswers: {},
      expertRound: 1,
      expertQuestions: [],
      expertConversationHistory: [],
      expertAnalysisBlocks: {},
      expertIsComplete: false,
      expertBlocksFilled: 0,
      solution: null,
      loading: false,
      error: null,
    }),
}))

export default useStore
