import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { Meeting, CreateMeetingRequest } from '../types';
import { meetingApi } from '../services/api';

interface MeetingContextType {
  // Data
  meetings: Meeting[];
  currentMeeting: Meeting | null;
  currentMeetingId: string | null;
  currentMeetingMode: 'view' | 'join';

  // Actions
  createMeeting: (data: CreateMeetingRequest) => Promise<Meeting | null>;
  selectMeeting: (meetingId: string) => Promise<boolean>;
  joinMeeting: (meetingId: string) => Promise<boolean>;
  leaveMeeting: () => void;
  refreshMeetings: () => Promise<void>;
  deleteMeeting: (meetingId: string) => Promise<void>;
  updateMeetingKeywords: (meetingId: string, keywords: string[]) => void;

  // Status
  isInActiveMeeting: boolean;
  isLoading: boolean;
  error: string | null;
}

const MeetingContext = createContext<MeetingContextType | undefined>(undefined);

interface MeetingProviderProps {
  children: ReactNode;
}

export const MeetingProvider: React.FC<MeetingProviderProps> = ({ children }) => {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [currentMeetingId, setCurrentMeetingId] = useState<string | null>(null);
  const [currentMeeting, setCurrentMeeting] = useState<Meeting | null>(null);
  const [currentMeetingMode, setCurrentMeetingMode] = useState<'view' | 'join'>('view');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isInActiveMeeting = currentMeetingMode === 'join' && currentMeetingId !== null;

  // Create a new meeting
  const createMeeting = useCallback(async (data: CreateMeetingRequest): Promise<Meeting | null> => {
    setIsLoading(true);
    setError(null);
    try {
      const newMeeting = await meetingApi.create(data);
      // Add to the beginning of the meetings list
      setMeetings(prev => [newMeeting, ...prev]);
      return newMeeting;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create meeting';
      setError(errorMessage);
      console.error('Failed to create meeting:', err);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load all meetings
  const refreshMeetings = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await meetingApi.getAll();
      setMeetings(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load meetings';
      setError(errorMessage);
      console.error('Failed to load meetings:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load a specific meeting's details
  const loadMeetingDetails = useCallback(async (meetingId: string): Promise<Meeting | null> => {
    try {
      const meeting = await meetingApi.getById(meetingId);
      return meeting;
    } catch (error) {
      console.error('Failed to load meeting details:', error);
      return null;
    }
  }, []);

  // Select a meeting (view mode) - No confirmation, just data operation
  const selectMeeting = useCallback(async (meetingId: string): Promise<boolean> => {
    // Load meeting details
    const meeting = await loadMeetingDetails(meetingId);
    if (!meeting) {
      return false;
    }

    setCurrentMeetingId(meetingId);
    setCurrentMeeting(meeting);
    setCurrentMeetingMode('view');
    return true;
  }, [loadMeetingDetails]);

  // Join a meeting (active mode with WebSocket) - No confirmation, just data operation
  const joinMeeting = useCallback(async (meetingId: string): Promise<boolean> => {
    // Load meeting details
    const meeting = await loadMeetingDetails(meetingId);
    if (!meeting) {
      return false;
    }

    setCurrentMeetingId(meetingId);
    setCurrentMeeting(meeting);
    setCurrentMeetingMode('join');
    return true;
  }, [loadMeetingDetails]);

  // Leave the current meeting
  const leaveMeeting = useCallback(() => {
    setCurrentMeetingId(null);
    setCurrentMeeting(null);
    setCurrentMeetingMode('view');
  }, []);

  // Delete a meeting
  const deleteMeeting = useCallback(async (meetingId: string) => {
    try {
      await meetingApi.delete(meetingId);
      setMeetings(prev => prev.filter(m => m.id !== meetingId));

      // If we deleted the current meeting, clear it
      if (currentMeetingId === meetingId) {
        leaveMeeting();
      }
    } catch (error) {
      console.error('Failed to delete meeting:', error);
      throw error;
    }
  }, [currentMeetingId, leaveMeeting]);

  // Update meeting keywords (optimistic update)
  const updateMeetingKeywords = useCallback((meetingId: string, keywords: string[]) => {
    // Update in meetings list
    setMeetings(prev =>
      prev.map(m => m.id === meetingId ? { ...m, keywords } : m)
    );

    // Update current meeting if it matches
    if (currentMeeting && currentMeeting.id === meetingId) {
      setCurrentMeeting({ ...currentMeeting, keywords });
    }
  }, [currentMeeting]);

  const value: MeetingContextType = {
    meetings,
    currentMeeting,
    currentMeetingId,
    currentMeetingMode,
    createMeeting,
    selectMeeting,
    joinMeeting,
    leaveMeeting,
    refreshMeetings,
    deleteMeeting,
    updateMeetingKeywords,
    isInActiveMeeting,
    isLoading,
    error,
  };

  return (
    <MeetingContext.Provider value={value}>
      {children}
    </MeetingContext.Provider>
  );
};

// Custom hook to use the meeting context
export const useMeetingContext = () => {
  const context = useContext(MeetingContext);
  if (context === undefined) {
    throw new Error('useMeetingContext must be used within a MeetingProvider');
  }
  return context;
};
