import { useState, useRef, useEffect } from 'react';

interface AudioRecorderProps {
  meetingId: string;
  websocket: WebSocket | null;
  onStatusChange?: (status: string) => void;
}

enum RecordingState {
  WAITING_FOR_SPEECH = 'waiting',
  RECORDING_SPEECH = 'recording',
  CONFIRMING_END = 'confirming_end'
}

export default function AudioRecorder({ meetingId, websocket, onStatusChange }: AudioRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [audioStatus, setAudioStatus] = useState<string>('idle');
  const [vadState, setVadState] = useState<RecordingState>(RecordingState.WAITING_FOR_SPEECH);
  const vadStateRef = useRef<RecordingState>(RecordingState.WAITING_FOR_SPEECH);
  const [currentVolume, setCurrentVolume] = useState<number>(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunkCountRef = useRef<number>(0);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyzerRef = useRef<AnalyserNode | null>(null);
  const processingIntervalRef = useRef<number | null>(null);
  const currentChunksRef = useRef<Blob[]>([]);
  const speechStartTimeRef = useRef<number>(0);
  const lastSpeechTimeRef = useRef<number>(0);
  const consecutiveSpeechTimeRef = useRef<number>(0);
  const consecutiveSilenceTimeRef = useRef<number>(0);

  // VAD Configuration Parameters
  const VAD_CONFIG = {
    SILENCE_THRESHOLD: 0.01,          // Volume below this = silence (0-1 range)
    SPEECH_START_DELAY_MS: 200,       // Require 200ms of speech to start recording
    SPEECH_END_DELAY_MS: 1000,        // Require 1s of silence to end recording
    MIN_CHUNK_DURATION_MS: 1000,      // Skip chunks shorter than 1s (filters coughs, clicks)
    MAX_CHUNK_DURATION_MS: 30000,     // Force-end chunks longer than 30s (prevent memory issues)
    CHECK_INTERVAL_MS: 100            // Check volume every 100ms
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (processingIntervalRef.current !== null) {
        clearInterval(processingIntervalRef.current);
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    // Notify parent of status changes
    if (onStatusChange) {
      onStatusChange(audioStatus);
    }
  }, [audioStatus, onStatusChange]);


  const sendAudioChunk = (chunk: Blob, duration: number) => {
    if (!websocket || websocket.readyState !== WebSocket.OPEN) {
      console.log('❌ WebSocket not available');
      return;
    }

    try {
      const chunkIndex = chunkCountRef.current++;
      websocket.send(chunk);
      console.log(`✅ Sent speech chunk ${chunkIndex}: ${chunk.size} bytes (${(duration / 1000).toFixed(1)}s)`);
    } catch (error) {
      console.error('❌ Error sending audio chunk:', error);
    }
  };

  const updateVadState = (newState: RecordingState) => {
    vadStateRef.current = newState;
    setVadState(newState);
  };

  const getVolume = (): number => {
    if (!analyzerRef.current) return 0;

    const bufferLength = analyzerRef.current.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyzerRef.current.getByteTimeDomainData(dataArray);

    let sum = 0;
    for (let i = 0; i < bufferLength; i++) {
      const normalized = Math.abs((dataArray[i] - 128) / 128);
      sum += normalized;
    }

    return sum / bufferLength;
  };

  const setupAudioAnalyzer = (stream: MediaStream) => {
    const audioContext = new AudioContext();
    const analyzer = audioContext.createAnalyser();
    const microphone = audioContext.createMediaStreamSource(stream);

    analyzer.fftSize = 2048;
    analyzer.smoothingTimeConstant = 0.8;
    microphone.connect(analyzer);

    audioContextRef.current = audioContext;
    analyzerRef.current = analyzer;
  };

  const startNewRecording = (stream: MediaStream) => {
    const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    currentChunksRef.current = [];

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        currentChunksRef.current.push(e.data);
      }
    };

    recorder.start();
    mediaRecorderRef.current = recorder;
    speechStartTimeRef.current = Date.now();
    lastSpeechTimeRef.current = Date.now();
  };

  const stopCurrentRecording = (stream: MediaStream): Promise<void> => {
    return new Promise((resolve) => {
      if (!mediaRecorderRef.current || mediaRecorderRef.current.state === 'inactive') {
        resolve();
        return;
      }

      const recordingDuration = Date.now() - speechStartTimeRef.current;

      mediaRecorderRef.current.onstop = () => {
        const speechBlob = new Blob(currentChunksRef.current, { type: 'audio/webm' });

        // Only send if chunk meets minimum duration
        if (recordingDuration >= VAD_CONFIG.MIN_CHUNK_DURATION_MS) {
          sendAudioChunk(speechBlob, recordingDuration);
        } else {
          console.log(`⏭️  Skipped short segment: ${(recordingDuration / 1000).toFixed(1)}s`);
        }

        // Check if we need to immediately start a new recording
        const volume = getVolume();
        const isSpeech = volume > VAD_CONFIG.SILENCE_THRESHOLD;

        if (isSpeech && isRecording) {
          // User is still speaking, start new recording immediately
          console.log('🔄 Continuing recording (max duration reached)');
          updateVadState(RecordingState.RECORDING_SPEECH);
          startNewRecording(stream);
        } else {
          // Return to waiting state
          updateVadState(RecordingState.WAITING_FOR_SPEECH);
          consecutiveSpeechTimeRef.current = 0;
          consecutiveSilenceTimeRef.current = 0;
        }

        resolve();
      };

      mediaRecorderRef.current.stop();
    });
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

      setAudioStatus('waiting-for-speech');
      setIsRecording(true);
      updateVadState(RecordingState.WAITING_FOR_SPEECH);

      // Reset counters
      chunkCountRef.current = 0;
      consecutiveSpeechTimeRef.current = 0;
      consecutiveSilenceTimeRef.current = 0;

      // Clear previous real-time transcription
      const clearRealTimeTranscription = (window as any)[`clearRealTimeTranscription_${meetingId}`];
      if (clearRealTimeTranscription) {
        clearRealTimeTranscription();
      }

      // Set up audio analyzer for volume detection
      setupAudioAnalyzer(stream);

      // Start VAD processing loop
      processingIntervalRef.current = window.setInterval(() => {
        const volume = getVolume();
        const isSpeech = volume > VAD_CONFIG.SILENCE_THRESHOLD;
        const now = Date.now();
        const currentState = vadStateRef.current;

        // Update UI with current volume
        setCurrentVolume(volume);

        console.log(`🎤 Volume: ${(volume * 100).toFixed(1)}% | State: ${currentState} | Speech: ${isSpeech}`);

        switch (currentState) {
          case RecordingState.WAITING_FOR_SPEECH:
            setAudioStatus('waiting-for-speech');

            if (isSpeech) {
              consecutiveSpeechTimeRef.current += VAD_CONFIG.CHECK_INTERVAL_MS;
              consecutiveSilenceTimeRef.current = 0;

              // Require sustained speech before starting
              if (consecutiveSpeechTimeRef.current >= VAD_CONFIG.SPEECH_START_DELAY_MS) {
                console.log('🟢 Speech detected - starting recording');
                updateVadState(RecordingState.RECORDING_SPEECH);
                setAudioStatus('recording-speech');
                startNewRecording(stream);
              }
            } else {
              consecutiveSpeechTimeRef.current = 0;
              consecutiveSilenceTimeRef.current = 0;
            }
            break;

          case RecordingState.RECORDING_SPEECH:
            setAudioStatus('recording-speech');

            if (isSpeech) {
              lastSpeechTimeRef.current = now;
              consecutiveSilenceTimeRef.current = 0;
            } else {
              consecutiveSilenceTimeRef.current += VAD_CONFIG.CHECK_INTERVAL_MS;
            }

            const recordingDuration = now - speechStartTimeRef.current;
            const silenceDuration = now - lastSpeechTimeRef.current;

            // Check if we should end recording due to silence
            if (silenceDuration >= VAD_CONFIG.SPEECH_END_DELAY_MS) {
              console.log('🔴 Silence detected - ending recording');
              updateVadState(RecordingState.CONFIRMING_END);
              setAudioStatus('processing');
              stopCurrentRecording(stream);
            }
            // Force-end if recording is too long
            else if (recordingDuration >= VAD_CONFIG.MAX_CHUNK_DURATION_MS) {
              console.log('⚠️  Max duration reached - force ending recording');
              updateVadState(RecordingState.CONFIRMING_END);
              setAudioStatus('processing');
              stopCurrentRecording(stream);
            }
            break;

          case RecordingState.CONFIRMING_END:
            setAudioStatus('processing');
            // Wait for recorder to stop (handled in stopCurrentRecording callback)
            break;
        }
      }, VAD_CONFIG.CHECK_INTERVAL_MS);

    } catch (error) {
      console.error('Failed to start audio recording:', error);
      setAudioStatus('error');
      alert('Failed to access microphone');
    }
  };

  const stopRecording = () => {
    // Clear the VAD processing interval
    if (processingIntervalRef.current !== null) {
      clearInterval(processingIntervalRef.current);
      processingIntervalRef.current = null;
    }

    // Stop any active recording
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }

    // Close audio context
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    setIsRecording(false);
    setAudioStatus('stopped');
    updateVadState(RecordingState.WAITING_FOR_SPEECH);
    setCurrentVolume(0);

    console.log('🛑 Recording stopped');
  };


  const getStatusDisplay = () => {
    switch (audioStatus) {
      case 'requesting-permission':
        return '🎙️ Requesting microphone permission...';
      case 'waiting-for-speech':
        return '🔇 Waiting for speech...';
      case 'recording-speech':
        return '🔴 Recording speech';
      case 'processing':
        return '⚙️ Processing chunk...';
      case 'stopped':
        return '⏹️ Stopped';
      case 'error':
        return '❌ Error';
      default:
        return '⏸️ Idle';
    }
  };

  const getVolumeBarWidth = () => {
    return Math.min(currentVolume * 100 * 10, 100); // Scale up for visibility
  };

  return (
    <div className="audio-recorder">
      <h3>Voice Activity Detection</h3>
      <div className="audio-controls">
        <div className="audio-status">
          <div className="status-text">
            Status: <span className={`status-indicator ${audioStatus}`}>{getStatusDisplay()}</span>
          </div>

          {isRecording && (
            <>
              <div className="vad-state">
                VAD State: <strong>{vadState}</strong>
              </div>

              <div className="volume-meter">
                <div className="volume-label">Volume:</div>
                <div className="volume-bar-container">
                  <div
                    className="volume-bar"
                    style={{
                      width: `${getVolumeBarWidth()}%`,
                      backgroundColor: currentVolume > VAD_CONFIG.SILENCE_THRESHOLD ? '#4CAF50' : '#ddd'
                    }}
                  />
                </div>
                <div className="volume-value">{(currentVolume * 100).toFixed(1)}%</div>
              </div>

              <div className="vad-info">
                <small>
                  Threshold: {(VAD_CONFIG.SILENCE_THRESHOLD * 100).toFixed(1)}% |
                  Start delay: {VAD_CONFIG.SPEECH_START_DELAY_MS}ms |
                  End delay: {VAD_CONFIG.SPEECH_END_DELAY_MS}ms
                </small>
              </div>
            </>
          )}
        </div>

        {!isRecording ? (
          <button
            onClick={startRecording}
            className="start-recording-btn"
            disabled={audioStatus === 'requesting-permission'}
          >
            {audioStatus === 'requesting-permission' ? 'Requesting Permission...' : 'Start VAD Recording'}
          </button>
        ) : (
          <button onClick={stopRecording} className="stop-recording-btn">
            Stop Recording
          </button>
        )}
      </div>

      <div className="vad-help">
        <details>
          <summary>ℹ️ How VAD works</summary>
          <ul style={{ fontSize: '0.9em', marginTop: '10px' }}>
            <li>🎤 Microphone monitors audio volume continuously</li>
            <li>🟢 Recording starts after {VAD_CONFIG.SPEECH_START_DELAY_MS}ms of speech</li>
            <li>🔴 Recording stops after {VAD_CONFIG.SPEECH_END_DELAY_MS}ms of silence</li>
            <li>⏭️ Chunks shorter than {VAD_CONFIG.MIN_CHUNK_DURATION_MS / 1000}s are skipped</li>
            <li>✂️ Long recordings auto-split at {VAD_CONFIG.MAX_CHUNK_DURATION_MS / 1000}s</li>
            <li>💰 Only speech is sent - saves transcription costs!</li>
          </ul>
        </details>
      </div>
    </div>
  );
}