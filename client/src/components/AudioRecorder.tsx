import { useState, useRef, useEffect } from 'react';

interface AudioRecorderProps {
  meetingId: string;
  websocket: WebSocket | null;
  onStatusChange?: (status: string) => void;
}

export default function AudioRecorder({ meetingId, websocket, onStatusChange }: AudioRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [audioStatus, setAudioStatus] = useState<string>('idle');
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunkCountRef = useRef<number>(0);
  
  // Audio chunk duration in milliseconds (5 seconds)
  const CHUNK_DURATION_MS = 5000;

  useEffect(() => {
    return () => {
      // Cleanup on unmount - only stop recording, don't touch websocket
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  useEffect(() => {
    // Notify parent of status changes
    if (onStatusChange) {
      onStatusChange(audioStatus);
    }
  }, [audioStatus, onStatusChange]);


  const sendAudioChunk = (chunk: Blob) => {
    if (!websocket || websocket.readyState !== WebSocket.OPEN) {
      console.log('❌ WebSocket not available');
      return;
    }
    
    try {
      const chunkIndex = chunkCountRef.current++;
      websocket.send(chunk);
      console.log(`✅ Sent audio chunk ${chunkIndex}: ${chunk.size} bytes`);
    } catch (error) {
      console.error('❌ Error sending audio chunk:', error);
    }
  };

  const startRecording = async () => {
    if (!meetingId) {
      alert('No meeting selected');
      return;
    }

    if (!websocket || websocket.readyState !== WebSocket.OPEN) {
      alert('WebSocket connection not available');
      return;
    }

    try {
      setAudioStatus('requesting-permission');
      
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      setAudioStatus('connected');
      setIsRecording(true);
      
      // Reset chunk counter for new recording
      chunkCountRef.current = 0;
      
      // Clear previous real-time transcription
      const clearRealTimeTranscription = (window as any)[`clearRealTimeTranscription_${meetingId}`];
      if (clearRealTimeTranscription) {
        clearRealTimeTranscription();
      }
      
      // Start recording
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm'
      });
      mediaRecorderRef.current = mediaRecorder;
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          console.log(`📦 Audio chunk received: ${event.data.size} bytes`);
          sendAudioChunk(event.data);
        }
      };
      
      // Generate audio chunks using chunk duration
      mediaRecorder.start(CHUNK_DURATION_MS);
      
    } catch (error) {
      console.error('Failed to start audio recording:', error);
      setAudioStatus('error');
      alert('Failed to access microphone');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      // Add event listener for the final chunk before stopping
      mediaRecorderRef.current.onstop = () => {
        console.log('📋 MediaRecorder stopped - final chunk should have been sent');
      };
      
      // Stop recording - this will trigger one final ondataavailable event
      mediaRecorderRef.current.stop();
    }
    
    setIsRecording(false);
    setAudioStatus('recording_stopped');
  };


  return (
    <div className="audio-recorder">
      <h3>Audio Recording</h3>
      <div className="audio-controls">
        <div className="audio-status">
          Status: <span className={`status-indicator ${audioStatus}`}>{audioStatus}</span>
        </div>
        {!isRecording ? (
          <button 
            onClick={startRecording} 
            className="start-recording-btn"
            disabled={audioStatus === 'requesting-permission' || audioStatus === 'connecting'}
          >
            {audioStatus === 'requesting-permission' ? 'Requesting Permission...' :
             audioStatus === 'connecting' ? 'Connecting...' : 'Start Recording'}
          </button>
        ) : (
          <button onClick={stopRecording} className="stop-recording-btn">
            Stop Recording
          </button>
        )}
      </div>
    </div>
  );
}