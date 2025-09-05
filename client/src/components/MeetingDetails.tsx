import { useState, useEffect, useRef } from 'react';
import { meetingApi } from '../services/api';
import { Meeting } from '../types';
import AudioRecorder from './AudioRecorder';
import RealTimeTranscription from './RealTimeTranscription';

interface MeetingDetailsProps {
  meetingId: string;
  onClose?: () => void;
}

export default function MeetingDetails({ meetingId, onClose }: MeetingDetailsProps) {
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingKeywords, setEditingKeywords] = useState(false);
  const [keywordInput, setKeywordInput] = useState('');
  const [localKeywords, setLocalKeywords] = useState<string[]>([]);
  const [audioStatus, setAudioStatus] = useState<string>('idle');
  const [websocket, setWebsocket] = useState<WebSocket | null>(null);
  const websocketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    loadMeetingDetails();
  }, [meetingId]);

  useEffect(() => {
    if (meeting) {
      setLocalKeywords(meeting.keywords || []);
    }
  }, [meeting]);

  useEffect(() => {
    if (meetingId) {
      connectWebSocket();
    }

    // Add event listener for window close/refresh
    const handleBeforeUnload = () => {
      if (websocketRef.current) {
        websocketRef.current.close();
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      if (websocketRef.current) {
        websocketRef.current.close();
      }
    };
  }, [meetingId]);

  const connectWebSocket = () => {
    if (websocketRef.current) {
      websocketRef.current.close();
    }

    const wsUrl = `${(import.meta as any).env.VITE_WS_URL || 'ws://localhost:8000'}/ws/meeting/${meetingId}/audio`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      // Skip processing if the message is binary data (audio chunks)
      if (event.data instanceof ArrayBuffer || event.data instanceof Blob) {
        return;
      }

      // Only process text messages that should be JSON
      if (typeof event.data === 'string') {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'transcription_status' && data.status === 'completed' && data.data?.full_text) {
            // Call the global function that RealTimeTranscription component expects
            const addTranscriptionFunction = (window as any)[`addRealTimeTranscription_${meetingId}`];
            if (addTranscriptionFunction) {
              addTranscriptionFunction(data.data.full_text);
            }
            console.log('📝 Transcription received:', data.data.full_text);
          }
          
          // Log all transcription status messages for debugging
          if (data.type === 'transcription_status') {
            console.log(`📡 Transcription status: ${data.status} - ${data.message}`);
          }
        } catch (error) {
          // Only log error for strings that should be JSON but aren't
          if (event.data.startsWith('{') || event.data.startsWith('[')) {
            console.error('Error parsing WebSocket JSON message:', error);
          }
        }
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = (event) => {
      console.log('WebSocket closed:', event.code, event.reason);
    };

    websocketRef.current = ws;
    setWebsocket(ws);
  };


  const loadMeetingDetails = async () => {
    if (!meetingId) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await meetingApi.getById(meetingId);
      setMeeting(data);
    } catch (error) {
      console.error('Failed to load meeting details:', error);
      setError('Failed to load meeting details');
    } finally {
      setLoading(false);
    }
  };

  const addKeyword = () => {
    if (keywordInput.trim() && !localKeywords.includes(keywordInput.trim())) {
      setLocalKeywords([...localKeywords, keywordInput.trim()]);
      setKeywordInput('');
    }
  };

  const removeKeyword = (keyword: string) => {
    setLocalKeywords(localKeywords.filter(k => k !== keyword));
  };

  const saveKeywords = async () => {
    try {
      const updatedMeeting = await meetingApi.updateKeywords(meetingId, localKeywords);
      setMeeting(updatedMeeting);
      setEditingKeywords(false);
    } catch (error) {
      console.error('Failed to update keywords:', error);
      alert('Failed to update keywords');
    }
  };

  const cancelKeywordEdit = () => {
    setLocalKeywords(meeting?.keywords || []);
    setKeywordInput('');
    setEditingKeywords(false);
  };

  const handleAudioStatusChange = (status: string) => {
    setAudioStatus(status);
  };

  if (!meetingId) {
    return (
      <div className="meeting-details">
        <div className="meeting-details-placeholder">
          <p>Select a meeting to view details</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="meeting-details">
        <div className="meeting-details-loading">
          <p>Loading meeting details...</p>
        </div>
      </div>
    );
  }

  if (error || !meeting) {
    return (
      <div className="meeting-details">
        <div className="meeting-details-error">
          <p>{error || 'Meeting not found'}</p>
          <button onClick={loadMeetingDetails}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="meeting-details">
      <div className="meeting-details-header">
        <h2>{meeting.title}</h2>
        {onClose && (
          <button onClick={onClose} className="close-btn">
            ×
          </button>
        )}
      </div>

      <div className="meeting-details-content">
        {meeting.description && (
          <div className="description-section">
            <h3>Description</h3>
            <p>{meeting.description}</p>
          </div>
        )}

        <div className="keywords-section">
          <div className="keywords-header">
            <h3>Keywords</h3>
            {!editingKeywords ? (
              <button onClick={() => setEditingKeywords(true)} className="edit-btn">
                Edit
              </button>
            ) : (
              <div className="keywords-actions">
                <button onClick={saveKeywords} className="save-btn">
                  Save
                </button>
                <button onClick={cancelKeywordEdit} className="cancel-btn">
                  Cancel
                </button>
              </div>
            )}
          </div>
          
          {editingKeywords ? (
            <div className="keywords-edit">
              <div className="keywords-input">
                <input
                  type="text"
                  value={keywordInput}
                  onChange={(e) => setKeywordInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addKeyword())}
                  placeholder="Add keyword and press Enter"
                />
                <button type="button" onClick={addKeyword}>Add</button>
              </div>
              <div className="keywords-list">
                {localKeywords.map((keyword) => (
                  <span key={keyword} className="keyword-tag">
                    {keyword}
                    <button type="button" onClick={() => removeKeyword(keyword)}>×</button>
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <div className="keywords-list">
              {localKeywords.length > 0 ? (
                localKeywords.map((keyword) => (
                  <span key={keyword} className="keyword-tag">
                    {keyword}
                  </span>
                ))
              ) : (
                <p className="no-keywords">No keywords set</p>
              )}
            </div>
          )}
        </div>

        <AudioRecorder 
          meetingId={meetingId} 
          websocket={websocket}
          onStatusChange={handleAudioStatusChange}
        />

        <RealTimeTranscription meetingId={meetingId} />

        {meeting.fullTranscription && (
          <div className="transcription-section">
            <h3>Full Transcription</h3>
            <div className="transcription-content">
              <pre>{meeting.fullTranscription}</pre>
            </div>
          </div>
        )}

        {meeting.metadata && (
          <div className="metadata-section">
            <h3>Metadata</h3>
            <div className="metadata-grid">
              {meeting.metadata.language && (
                <div className="metadata-item">
                  <label>Language:</label>
                  <span>{meeting.metadata.language}</span>
                </div>
              )}
              {meeting.metadata.participants && meeting.metadata.participants.length > 0 && (
                <div className="metadata-item">
                  <label>Participants:</label>
                  <span>{meeting.metadata.participants.join(', ')}</span>
                </div>
              )}
              {meeting.metadata.totalDuration && (
                <div className="metadata-item">
                  <label>Duration:</label>
                  <span>{Math.round(meeting.metadata.totalDuration / 60)} minutes</span>
                </div>
              )}
              {meeting.metadata.processingStarted && (
                <div className="metadata-item">
                  <label>Processing Started:</label>
                  <span>{new Date(meeting.metadata.processingStarted).toLocaleString()}</span>
                </div>
              )}
              {meeting.metadata.processingCompleted && (
                <div className="metadata-item">
                  <label>Processing Completed:</label>
                  <span>{new Date(meeting.metadata.processingCompleted).toLocaleString()}</span>
                </div>
              )}
              {meeting.metadata.totalProcessingTime && (
                <div className="metadata-item">
                  <label>Processing Time:</label>
                  <span>{meeting.metadata.totalProcessingTime} seconds</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}