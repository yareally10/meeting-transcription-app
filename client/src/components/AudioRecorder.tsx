import { useState, useRef, useEffect } from 'react';

interface AudioRecorderProps {
  meetingId: string;
  onStatusChange?: (status: string) => void;
}

export default function AudioRecorder({ meetingId, onStatusChange }: AudioRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [audioStatus, setAudioStatus] = useState<string>('idle');
  
  const websocketRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);

  useEffect(() => {
    return () => {
      // Cleanup on unmount
      if (websocketRef.current) {
        websocketRef.current.close();
      }
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
    if (!websocketRef.current || websocketRef.current.readyState !== WebSocket.OPEN) {
      console.log('❌ WebSocket not available');
      return;
    }
    
    try {
      websocketRef.current.send(chunk);
      console.log(`✅ Sent audio chunk: ${chunk.size} bytes`);
    } catch (error) {
      console.error('❌ Error sending audio chunk:', error);
    }
  };

  const startRecording = async () => {
    if (!meetingId) {
      alert('No meeting selected');
      return;
    }

    try {
      setAudioStatus('requesting-permission');
      
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      setAudioStatus('connecting');
      
      // Create WebSocket connection
      const ws = new WebSocket(`ws://localhost:8000/ws/meeting/${meetingId}/audio`);
      websocketRef.current = ws;
      
      ws.onopen = () => {
        setAudioStatus('connected');
        setIsRecording(true);
        
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
        
        // Generate audio chunks every 1 second
        mediaRecorder.start(1000);
      };
      
      ws.onmessage = (event) => {
        console.log('Received from server:', event.data);
      };
      
      ws.onclose = () => {
        setAudioStatus('disconnected');
        setIsRecording(false);
        stream.getTracks().forEach(track => track.stop());
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setAudioStatus('error');
        setIsRecording(false);
      };
      
    } catch (error) {
      console.error('Failed to start audio streaming:', error);
      setAudioStatus('error');
      alert('Failed to access microphone or start streaming');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    
    if (websocketRef.current) {
      websocketRef.current.close();
    }
    
    setIsRecording(false);
    setAudioStatus('idle');
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