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

  smartQuestions: null,
  setSmartQuestions: (smartQuestions) => set({ smartQuestions }),
  smartAnswers: {},
  setSmartAnswers: (smartAnswers) => set({ smartAnswers }),

  solution: null,
  setSolution: (solution) => set({ solution }),

  analysisBlocks: null,
  setAnalysisBlocks: (analysisBlocks) => set({ analysisBlocks }),

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
      smartQuestions: null,
      smartAnswers: {},
      solution: null,
      analysisBlocks: null,
      loading: false,
      error: null,
    }),
}))

export default useStore
