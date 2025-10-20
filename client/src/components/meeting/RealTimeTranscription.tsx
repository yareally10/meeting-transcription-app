import { useState, useEffect, useRef } from 'react';
import { matchKeywords } from '../../services/keywordMatcher';
import './RealTimeTranscription.css';

interface TranscriptionChunk {
  id: string;
  text: string;
  timestamp: Date;
}

interface RealTimeTranscriptionProps {
  meetingId: string;
  keywords?: string[];
}

export default function RealTimeTranscription({ meetingId, keywords = [] }: RealTimeTranscriptionProps) {
  const [chunks, setChunks] = useState<TranscriptionChunk[]>([]);
  const [isActive, setIsActive] = useState(false);
  const transcriptionEndRef = useRef<HTMLDivElement>(null);

  const addTranscriptionChunk = (text: string) => {
    const chunk: TranscriptionChunk = {
      id: Math.random().toString(36).substr(2, 9),
      text: text.trim(),
      timestamp: new Date()
    };
    
    if (chunk.text) {
      setChunks(prev => [...prev, chunk]);
      setIsActive(true);
      
      // Auto-scroll to bottom
      setTimeout(() => {
        transcriptionEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    }
  };

  const clearTranscription = () => {
    setChunks([]);
    setIsActive(false);
  };

  const highlightKeywords = (text: string) => {
    const matches = matchKeywords(keywords, text);
    
    return matches.map((match, index) => {
      if (match.isKeyword) {
        return (
          <span key={index} className="highlighted-keyword">
            {match.text}
          </span>
        );
      }
      return match.text;
    });
  };

  // Expose the addTranscriptionChunk function globally for this meeting
  useEffect(() => {
    (window as any)[`addRealTimeTranscription_${meetingId}`] = addTranscriptionChunk;
    (window as any)[`clearRealTimeTranscription_${meetingId}`] = clearTranscription;
    
    return () => {
      delete (window as any)[`addRealTimeTranscription_${meetingId}`];
      delete (window as any)[`clearRealTimeTranscription_${meetingId}`];
    };
  }, [meetingId]);

  if (!isActive && chunks.length === 0) {
    return (
      <div className="real-time-transcription">
        <h3>Live Transcription</h3>
        <div className="transcription-placeholder">
          <p>Start recording to see live transcription...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="real-time-transcription">
      <div className="transcription-header">
        <h3>Live Transcription</h3>
        <div className="transcription-controls">
          <span className="transcription-status active">● LIVE</span>
          <button onClick={clearTranscription} className="clear-btn">
            Clear
          </button>
        </div>
      </div>
      
      <div className="transcription-content">
        {chunks.map((chunk) => (
          <div key={chunk.id} className="transcription-chunk">
            <span className="transcription-timestamp">
              {chunk.timestamp.toLocaleTimeString()}
            </span>
            <span className="transcription-text">{highlightKeywords(chunk.text)}</span>
          </div>
        ))}
        <div ref={transcriptionEndRef} />
      </div>
    </div>
  );
}