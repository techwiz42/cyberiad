// src/services/threads.ts
import { Thread, ThreadFormData, PaginatedResponse } from '@/types'
import { api, getAuthHeaders } from './api'

export const threadService = {
  async getThreads(token: string): Promise<PaginatedResponse<Thread>> {
    const response = await api.get<PaginatedResponse<Thread>>(
      '/api/threads',
      { headers: getAuthHeaders(token) }
    )
    return response.data!
  },

  async getThread(threadId: string, token: string): Promise<Thread> {
    const response = await api.get<Thread>(
      `/api/threads/${threadId}`,
      { headers: getAuthHeaders(token) }
    )
    return response.data!
  },

  async createThread(data: ThreadFormData, token: string): Promise<Thread> {
    const response = await api.post<Thread>(
      '/api/threads',
      { ...data }, // Convert ThreadFormData into a plain object
      { headers: getAuthHeaders(token) }
    );
    return response.data!;
  },

  async updateThread(
    threadId: string,
    data: Partial<ThreadFormData>,
    token: string
  ): Promise<Thread> {
    const response = await api.put<Thread>(
      `/api/threads/${threadId}`,
      data,
      { headers: getAuthHeaders(token) }
    )
    return response.data!
  },

  async deleteThread(threadId: string, token: string): Promise<void> {
    await api.delete(
      `/api/threads/${threadId}`,
      { headers: getAuthHeaders(token) }
    )
  },

  async inviteToThread(
    threadId: string,
    usernames: string[],
    token: string
  ): Promise<void> {
    await api.post(
      `/api/threads/${threadId}/invite`,
      { usernames },
      { headers: getAuthHeaders(token) }
    )
  }
}
