import axios from 'axios'

const API = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

export const api = {
  health:        ()              => API.get('/health'),
  predict:       (text)         => API.post('/predict', { text }),
  predictBatch:  (texts)        => API.post('/predict/batch', { texts }),
  analyzeReddit: (subreddit, limit = 15) =>
                                   API.get('/analyze/reddit', { params: { subreddit, limit } }),
  getAnalytics:  (subreddit='') => API.get('/analytics', { params: subreddit ? { subreddit } : {} }),
}

export default API
