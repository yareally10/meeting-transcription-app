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

  async function analyzeChunkMetadata(chunk: Blob | ArrayBuffer, isFirstChunk: boolean = false) {
  return {
    size: (chunk as Blob).size,
    type: (chunk as Blob).type,
    hasValidWebMStructure: await checkWebMStructure(chunk, isFirstChunk),
    issues: []
  };
}

async function checkWebMStructure(chunk: Blob | ArrayBuffer, isFirstChunk: boolean): Promise<boolean> {
  try {
    const arrayBuffer = chunk instanceof Blob ? 
      await chunk.arrayBuffer() : chunk;
    const data = new Uint8Array(arrayBuffer);
    
    if (data.length < 4) return false;
    
    if (isFirstChunk) {
      // First chunk should have EBML header
      return checkBytes(data, 0, [0x1A, 0x45, 0xDF, 0xA3]);
    } else {
      // Subsequent chunks should have Cluster or Segment headers
      return checkBytes(data, 0, [0x1F, 0x43, 0xB6, 0x75]) || // Cluster
             checkBytes(data, 0, [0x18, 0x53, 0x80, 0x67]);   // Segment
    }
  } catch (error) {
    return false;
  }
}

function checkBytes(data: Uint8Array, offset: number, signature: number[]): boolean {
  if (offset + signature.length > data.length) return false;
  return signature.every((byte, index) => 
    data[offset + index] === byte
  );
}

function createWebMHeaders(): Uint8Array {
  // Create Cluster header (0x1F43B675) and Segment header (0x18538067)
  const clusterHeader = new Uint8Array([0x1A, 0x45, 0xDF, 0xA3]);
  const segmentHeader = new Uint8Array([0x93, 0x42, 0x82]);
  
  // Combine both headers
  return combineUint8Arrays(segmentHeader, clusterHeader);
  //return new Uint8Array([0x1A, 0x45, 0xDF, 0xA3]);
}

function combineUint8Arrays(array1: Uint8Array, array2: Uint8Array): Uint8Array {
  const combined = new Uint8Array(array1.length + array2.length);
  combined.set(array1, 0);
  combined.set(array2, array1.length);
  return combined;
}

  const sendAudioChunk = async (chunk: Blob) => {
    if (!websocket || websocket.readyState !== WebSocket.OPEN) {
      console.log('❌ WebSocket not available');
      return;
    }
    
    try {
      const chunkIndex = chunkCountRef.current++;
      const isFirstChunk = chunkIndex === 0;
      
      let finalChunk = chunk;
      
      if (!isFirstChunk) {
        // For subsequent chunks, prepend the WebM headers
        const chunkData = new Uint8Array(await chunk.arrayBuffer());
        const webmHeaders = createWebMHeaders();
        const combinedData = combineUint8Arrays(webmHeaders, chunkData);
        finalChunk = new Blob([new Uint8Array(combinedData)], { type: chunk.type });
        console.log(`🔗 Added WebM headers + chunk: ${webmHeaders.length} + ${chunkData.length} = ${combinedData.length} bytes`);
      }
      
      const metadata = await analyzeChunkMetadata(finalChunk, isFirstChunk);
      console.log(`📊 Chunk ${chunkIndex}:`, JSON.stringify(metadata));
      
      websocket.send(chunk);
      console.log(`✅ Sent audio chunk ${chunkIndex}: ${finalChunk.size} bytes`);
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
      
      mediaRecorder.ondataavailable = async (event) => {
        if (event.data.size > 0) {
          console.log(`📦 Audio chunk received: ${event.data.size} bytes`);
          await sendAudioChunk(event.data);
        }
      };
      
      // Generate audio chunks every 5 seconds
      mediaRecorder.start(5000);
      
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