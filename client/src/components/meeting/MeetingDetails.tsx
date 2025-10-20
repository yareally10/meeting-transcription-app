import { useState, useEffect, useRef } from 'react';
import { meetingApi } from '../../services/api';
import { Meeting } from '../../types';
import AudioRecorder from './AudioRecorder';
import RealTimeTranscription from './RealTimeTranscription';
import KeywordsManager from './KeywordsManager';
import './MeetingDetails.css';

interface MeetingDetailsProps {
  meetingId: string;
  mode?: 'view' | 'join'; // 'view' shows only basic info, 'join' shows full meeting interface
  onClose?: () => void;
}

export default function MeetingDetails({ meetingId, mode = 'view', onClose }: MeetingDetailsProps) {
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [websocket, setWebsocket] = useState<WebSocket | null>(null);
  const websocketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    loadMeetingDetails();
  }, [meetingId]);


  useEffect(() => {
    // Only connect WebSocket in 'join' mode
    if (meetingId && mode === 'join') {
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
  }, [meetingId, mode]);

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

  const handleKeywordsUpdated = (newKeywords: string[]) => {
    if (meeting) {
      setMeeting({ ...meeting, keywords: newKeywords });
    }
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

  // Render in 'view' mode: only title, description, and keywords (read-only)
  if (mode === 'view') {
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
          <div className="description-section">
            <h3>Description</h3>
            <p>{meeting.description ? meeting.description : 'none'}</p>
          </div>


          {meeting.keywords && meeting.keywords.length > 0 && (
            <div className="keywords-section">
              <h3>Keywords</h3>
              <div className="keywords-list-readonly">
                {meeting.keywords.map((keyword, index) => (
                  <span key={index} className="keyword-tag-readonly">
                    {keyword}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Render in 'join' mode: full meeting interface with audio recorder and transcription
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
          <h3>Keywords</h3>
          <KeywordsManager
            meetingId={meetingId}
            currentKeywords={meeting?.keywords || []}
            onKeywordsUpdated={handleKeywordsUpdated}
            showTitle={false}
          />
        </div>

        <AudioRecorder
          meetingId={meetingId}
          websocket={websocket}
        />

        <RealTimeTranscription meetingId={meetingId} keywords={meeting?.keywords || []} />

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