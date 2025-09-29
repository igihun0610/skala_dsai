import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { Notify } from 'quasar'

// API Response wrapper
export interface ApiResponse<T = any> {
  data: T
  message?: string
  status: number
}

// Error response structure
export interface ApiError {
  detail: string
  status: number
  timestamp: string
}

// Create axios instance with default config
const apiClient: AxiosInstance = axios.create({
  baseURL: '/api', // Proxied through Vite to http://localhost:8000/api
  timeout: 120000, // 2 minutes for long operations
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add request timestamp for debugging
    config.metadata = { startTime: new Date() }

    // Log requests in development
    if (import.meta.env.DEV) {
      console.log(`🔵 API Request: ${config.method?.toUpperCase()} ${config.url}`, {
        params: config.params,
        data: config.data && !(config.data instanceof FormData) ? config.data : '[FormData]'
      })
    }

    return config
  },
  (error) => {
    console.error('API Request Error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    // Calculate request duration
    const endTime = new Date()
    const startTime = response.config.metadata?.startTime || endTime
    const duration = endTime.getTime() - startTime.getTime()

    // Log responses in development
    if (import.meta.env.DEV) {
      console.log(`🟢 API Response: ${response.config.method?.toUpperCase()} ${response.config.url} (${duration}ms)`, {
        status: response.status,
        data: response.data
      })
    }

    return response
  },
  (error) => {
    // Calculate request duration for failed requests
    const endTime = new Date()
    const startTime = error.config?.metadata?.startTime || endTime
    const duration = endTime.getTime() - startTime.getTime()

    let errorMessage = '알 수 없는 오류가 발생했습니다.'
    let errorDetail = ''

    if (error.response) {
      // Server responded with error status
      const status = error.response.status
      const data = error.response.data

      console.error(`🔴 API Error: ${error.config?.method?.toUpperCase()} ${error.config?.url} (${duration}ms)`, {
        status,
        data
      })

      switch (status) {
        case 400:
          errorMessage = '잘못된 요청입니다.'
          errorDetail = data?.detail || '요청 데이터를 확인해주세요.'
          break
        case 401:
          errorMessage = '인증이 필요합니다.'
          errorDetail = '다시 로그인해주세요.'
          break
        case 403:
          errorMessage = '접근 권한이 없습니다.'
          errorDetail = '이 작업을 수행할 권한이 없습니다.'
          break
        case 404:
          errorMessage = '요청한 리소스를 찾을 수 없습니다.'
          errorDetail = 'API 엔드포인트를 확인해주세요.'
          break
        case 422:
          errorMessage = '입력 데이터 오류'
          errorDetail = data?.detail || '입력 형식을 확인해주세요.'
          break
        case 429:
          errorMessage = '요청이 너무 많습니다.'
          errorDetail = '잠시 후 다시 시도해주세요.'
          break
        case 500:
          errorMessage = '서버 내부 오류'
          errorDetail = '서버에 문제가 발생했습니다. 관리자에게 문의하세요.'
          break
        case 502:
        case 503:
          errorMessage = '서버를 사용할 수 없습니다.'
          errorDetail = '서버가 일시적으로 사용 불가능합니다.'
          break
        case 504:
          errorMessage = '요청 시간 초과'
          errorDetail = '서버 응답 시간이 초과되었습니다.'
          break
        default:
          errorMessage = `서버 오류 (${status})`
          errorDetail = data?.detail || '서버에서 오류가 발생했습니다.'
      }

      // Show user notification for certain errors
      if (status >= 500 || status === 404) {
        Notify.create({
          type: 'negative',
          message: errorMessage,
          caption: errorDetail,
          timeout: 5000,
          actions: [{ icon: 'close', color: 'white' }]
        })
      }

    } else if (error.request) {
      // Network error - no response received
      console.error('🔴 Network Error:', error.message)
      errorMessage = '네트워크 연결 오류'
      errorDetail = '서버에 연결할 수 없습니다. 네트워크 연결을 확인해주세요.'

      Notify.create({
        type: 'negative',
        message: errorMessage,
        caption: errorDetail,
        timeout: 5000,
        actions: [{ icon: 'close', color: 'white' }]
      })

    } else {
      // Request setup error
      console.error('🔴 Request Setup Error:', error.message)
      errorMessage = '요청 설정 오류'
      errorDetail = error.message
    }

    // Enhance error object
    const enhancedError = {
      ...error,
      message: errorMessage,
      detail: errorDetail,
      status: error.response?.status || 0,
      timestamp: new Date().toISOString()
    }

    return Promise.reject(enhancedError)
  }
)

// API wrapper class
class ApiService {
  private client: AxiosInstance

  constructor(client: AxiosInstance) {
    this.client = client
  }

  // GET request
  async get<T = any>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.get<T>(url, config)
  }

  // POST request
  async post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.post<T>(url, data, config)
  }

  // PUT request
  async put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.put<T>(url, data, config)
  }

  // PATCH request
  async patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.patch<T>(url, data, config)
  }

  // DELETE request
  async delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.delete<T>(url, config)
  }

  // Upload file with progress
  async uploadFile<T = any>(
    url: string,
    file: File,
    fieldName = 'file',
    additionalData?: Record<string, any>,
    onProgress?: (progress: number) => void
  ): Promise<AxiosResponse<T>> {
    const formData = new FormData()
    formData.append(fieldName, file)

    // Add additional data to form
    if (additionalData) {
      Object.entries(additionalData).forEach(([key, value]) => {
        if (value !== null && value !== undefined) {
          formData.append(key, String(value))
        }
      })
    }

    return this.client.post<T>(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(progress)
        }
      }
    })
  }

  // Download file
  async downloadFile(url: string, filename?: string): Promise<void> {
    try {
      const response = await this.client.get(url, {
        responseType: 'blob'
      })

      // Create blob URL
      const blob = new Blob([response.data])
      const downloadUrl = window.URL.createObjectURL(blob)

      // Create temporary link and trigger download
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = filename || 'download'
      document.body.appendChild(link)
      link.click()

      // Cleanup
      document.body.removeChild(link)
      window.URL.revokeObjectURL(downloadUrl)

    } catch (error) {
      console.error('Download failed:', error)
      throw error
    }
  }

  // Health check
  async healthCheck(): Promise<boolean> {
    try {
      const response = await this.client.get('/health')
      return response.data.status === 'healthy'
    } catch (error) {
      return false
    }
  }

  // Set default headers
  setDefaultHeader(key: string, value: string): void {
    this.client.defaults.headers.common[key] = value
  }

  // Remove default header
  removeDefaultHeader(key: string): void {
    delete this.client.defaults.headers.common[key]
  }

  // Update base URL
  setBaseURL(baseURL: string): void {
    this.client.defaults.baseURL = baseURL
  }

  // Update timeout
  setTimeout(timeout: number): void {
    this.client.defaults.timeout = timeout
  }
}

// Create and export API service instance
export const api = new ApiService(apiClient)

// Export axios instance for direct use if needed
export { apiClient }

// Type augmentation for axios config metadata
declare module 'axios' {
  interface AxiosRequestConfig {
    metadata?: {
      startTime: Date
    }
  }
}