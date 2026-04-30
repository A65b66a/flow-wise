import axios from 'axios'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
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

  guidedAnalysis: (userInput, scope, answers) =>
    http.post('/guided/analysis', { user_input: userInput, scope, answers: answers || {} }).then((r) => r.data),

  guidedComplete: (userInput, scope, answers) =>
    http
      .post('/guided/complete', { user_input: userInput, scope, answers })
      .then((r) => r.data),

  conversationalMessage: (userInput, scope, conversation, message, minQuestions = 5, sessionId = null) =>
    http
      .post('/guided/conversation/message', {
        user_input: userInput,
        scope,
        session_id: sessionId,
        conversation,
        message,
        min_questions: minQuestions,
      })
      .then((r) => r.data),

  conversationalReview: (userInput, scope, answers) =>
    http
      .post('/guided/conversation/review', { user_input: userInput, scope, answers: answers || {} })
      .then((r) => r.data),

  smartGuidedQuestions: (userInput, scope) =>
    http.post('/guided/smart/questions', { user_input: userInput, scope }).then((r) => r.data),

  smartGuidedComplete: (userInput, scope, answers) =>
    http
      .post('/guided/smart/complete', { user_input: userInput, scope, answers })
      .then((r) => r.data),

  guidedLoopStart: (userInput, scope, maxQuestions = 10) =>
    http
      .post('/guided/loop/start', { user_input: userInput, scope, max_questions: maxQuestions })
      .then((r) => r.data),

  guidedLoopAnswer: (sessionId, field, value) =>
    http
      .post('/guided/loop/answer', { session_id: sessionId, field, value })
      .then((r) => r.data),

  guidedLoopSession: (sessionId) =>
    http.get(`/guided/loop/session/${sessionId}`).then((r) => r.data),

  expertLoopStart: (userInput, scope, minQuestions = 20, maxQuestions = 60) =>
    http
      .post('/expert/loop/start', { user_input: userInput, scope, min_questions: minQuestions, max_questions: maxQuestions })
      .then((r) => r.data),

  expertLoopAnswer: (sessionId, field, value) =>
    http
      .post('/expert/loop/answer', { session_id: sessionId, field, value })
      .then((r) => r.data),

  expertLoopSession: (sessionId) =>
    http.get(`/expert/loop/session/${sessionId}`).then((r) => r.data),

  getTemplates: () => http.get('/templates').then((r) => r.data),
}
