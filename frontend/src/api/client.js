import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 120_000,
})

http.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg =
      err.response?.data?.detail ||
      err.response?.data?.message ||
      err.message ||
      'Unknown error'
    return Promise.reject(new Error(msg))
  }
)

export const api = {
  health: () => http.get('/health'),

  analyzeScope: (userInput) =>
    http.post('/scope', { user_input: userInput }).then((r) => r.data),

  selectMode: (userInput, scope) =>
    http.post('/mode', { user_input: userInput, scope }).then((r) => r.data),

  autoInit: (userInput, scope) =>
    http.post('/auto/init', { user_input: userInput, scope }).then((r) => r.data),

  autoComplete: (userInput, scope, autoPilotInit, quickInputs) =>
    http
      .post('/auto/complete', {
        user_input: userInput,
        scope,
        auto_pilot_init: autoPilotInit,
        quick_inputs: quickInputs,
      })
      .then((r) => r.data),

  guidedQuestions: (block, userInput, scope, previousAnswers) =>
    http
      .post(`/guided/questions/${block}`, {
        block,
        user_input: userInput,
        scope,
        previous_answers: previousAnswers || {},
      })
      .then((r) => r.data),

  guidedComplete: (userInput, scope, answers) =>
    http
      .post('/guided/complete', { user_input: userInput, scope, answers })
      .then((r) => r.data),

  expertQuestions: (userInput, scope, round, conversationHistory, analysisBlocks) =>
    http
      .post('/expert/questions', {
        user_input: userInput,
        scope,
        round,
        conversation_history: conversationHistory || [],
        analysis_blocks: analysisBlocks || {},
      })
      .then((r) => r.data),

  expertComplete: (userInput, scope, analysisBlocks) =>
    http
      .post('/expert/complete', {
        user_input: userInput,
        scope,
        analysis_blocks: analysisBlocks,
      })
      .then((r) => r.data),

  getTemplates: () => http.get('/templates').then((r) => r.data),
}
