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

// Unwraps BaseResponse envelope { success, message, data, error_code, type, details }
const unwrap = (r) => {
  const body = r.data
  if (!body) throw new Error('Empty response from server')
  // New BaseResponse format
  if ('success' in body) {
    if (!body.success) throw new Error(body.message || 'Request failed')
    return body.data
  }
  // Passthrough for any non-wrapped response
  return body
}

export const api = {
  health: () => http.get('/health').then(unwrap),

  analyzeScope: (userInput) =>
    http.post('/scope', { user_input: userInput }).then(unwrap),

  selectMode: (userInput, scope) =>
    http.post('/mode', { user_input: userInput, scope }).then(unwrap),

  autoInit: (userInput, scope) =>
    http.post('/auto/init', { user_input: userInput, scope }).then(unwrap),

  autoComplete: (userInput, scope, autoPilotInit, quickInputs) =>
    http
      .post('/auto/complete', {
        user_input: userInput,
        scope,
        auto_pilot_init: autoPilotInit,
        quick_inputs: quickInputs,
      })
      .then(unwrap),

  guidedQuestions: (block, userInput, scope, previousAnswers) =>
    http
      .post(`/guided/questions/${block}`, {
        block,
        user_input: userInput,
        scope,
        previous_answers: previousAnswers || {},
      })
      .then(unwrap),

  guidedComplete: (userInput, scope, answers) =>
    http
      .post('/guided/complete', { user_input: userInput, scope, answers })
      .then(unwrap),

  expertQuestions: (userInput, scope, round, conversationHistory, analysisBlocks) =>
    http
      .post('/expert/questions', {
        user_input: userInput,
        scope,
        round,
        conversation_history: conversationHistory || [],
        analysis_blocks: analysisBlocks || {},
      })
      .then(unwrap),

  expertComplete: (userInput, scope, analysisBlocks) =>
    http
      .post('/expert/complete', {
        user_input: userInput,
        scope,
        analysis_blocks: analysisBlocks,
      })
      .then(unwrap),

  getTemplates: () => http.get('/templates').then(unwrap),
}
