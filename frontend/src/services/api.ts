// src/services/api.ts
import { ApiResponse } from '@/types'

const API_BASE_URL = 'http://cyberiad.ai:8000'

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const fullUrl = `${API_BASE_URL}${endpoint}`
  console.log('Making fetch request to:', fullUrl)
  
  try {
    const response = await fetch(fullUrl, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...options.headers,
      },
    })

    const data = await response.json()
    
    if (!response.ok) {
      console.error('API Error:', {
        status: response.status,
        data
      })
      throw new ApiError(
        response.status,
        data.detail || 'An error occurred'
      )
    }

    return { data }
  } catch (err) {
    if (err instanceof ApiError) {
      throw err
    }
    console.error('Fetch error:', err)
    throw new Error(err instanceof Error ? err.message : 'Network request failed')
  }
}

export const api = {
  get: <T>(endpoint: string, options?: RequestInit) => 
    fetchApi<T>(endpoint, { ...options, method: 'GET' }),
    
  post: <T>(endpoint: string, data?: unknown, options?: RequestInit) => {
    console.log('Making POST request:', {
      endpoint,
      data: data instanceof URLSearchParams ? data.toString() : data,
      options
    })
    
    const body = data instanceof URLSearchParams ? 
      data : 
      JSON.stringify(data)
    
    return fetchApi<T>(endpoint, {
      ...options,
      method: 'POST',
      body,
    })
  },
    
  put: <T>(endpoint: string, data?: unknown, options?: RequestInit) =>
    fetchApi<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(data),
    }),
    
  delete: <T>(endpoint: string, options?: RequestInit) =>
    fetchApi<T>(endpoint, { ...options, method: 'DELETE' }),
}

export function getAuthHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
  }
}
