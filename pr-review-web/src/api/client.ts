/**
 * Axios API Client for PR Review Web Interface
 */

import axios from 'axios'

// Determine base URL based on current location
// If served from the same origin, use relative URLs
// Otherwise, use the configured backend URL
const getBaseURL = () => {
  // Check if we're in development mode (Vite dev server)
  // @ts-ignore - import.meta.env.DEV is set by Vite
  if (import.meta.env?.DEV) {
    return 'http://127.0.0.1:8000'
  }
  // In production, use relative URL (same origin)
  return ''
}

const baseURL = getBaseURL()

console.log('API Client Base URL:', baseURL || '(relative - same origin)')

const apiClient = axios.create({
  baseURL: baseURL,
  headers: {
    'Content-Type': 'application/json'
  },
  timeout: 120000 // 2 minutes - analysis tasks run in background, but this handles edge cases
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    console.log('API Request:', config.method?.toUpperCase(), config.url)
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
apiClient.interceptors.response.use(
  (response) => {
    console.log('API Response:', response.status, response.config.url)
    return response
  },
  (error) => {
    if (error.response) {
      // Server responded with error status
      console.error('API Error:', error.response.status, error.response.data)
      return Promise.reject(error.response.data)
    } else if (error.request) {
      // Request made but no response
      console.error('Network Error:', error.message)
      console.error('Request was made but no response received')
      console.error('Base URL being used:', baseURL)
      return Promise.reject({ message: 'Network error. Is the backend running?' })
    } else {
      console.error('Error:', error.message)
      return Promise.reject(error)
    }
  }
)

export default apiClient
