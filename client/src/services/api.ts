import axios from 'axios';
import { Meeting, CreateMeetingRequest, UpdateMeetingRequest } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const meetingApi = {
  create: async (meeting: CreateMeetingRequest): Promise<Meeting> => {
    const response = await api.post('/meetings', meeting);
    return response.data;
  },

  getAll: async (): Promise<Meeting[]> => {
    const response = await api.get('/meetings');
    return response.data;
  },

  getById: async (id: string): Promise<Meeting> => {
    const response = await api.get(`/meetings/${id}`);
    return response.data;
  },

  update: async (id: string, updates: UpdateMeetingRequest): Promise<Meeting> => {
    const response = await api.put(`/meetings/${id}`, updates);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/meetings/${id}`);
  },

  updateKeywords: async (id: string, keywords: string[]): Promise<Meeting> => {
    const response = await api.put(`/meetings/${id}/keywords`, { keywords });
    return response.data;
  },
};