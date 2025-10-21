import { useState, useEffect } from 'react';
import { meetingApi } from '../../services/api';
import './KeywordsManager.css';

interface KeywordsManagerProps {
  meetingId?: string; // Optional for creation mode
  currentKeywords: string[];
  onKeywordsUpdated: (keywords: string[]) => void;
  disabled?: boolean;
  showTitle?: boolean;
}

export default function KeywordsManager({ 
  meetingId, 
  currentKeywords, 
  onKeywordsUpdated, 
  disabled = false,
  showTitle = true 
}: KeywordsManagerProps) {
  const [keywords, setKeywords] = useState<string[]>(currentKeywords);
  const [keywordInput, setKeywordInput] = useState('');
  const [loading, setLoading] = useState(false);

  // Update keywords when currentKeywords prop changes
  useEffect(() => {
    setKeywords(currentKeywords);
  }, [currentKeywords]);

  const addKeyword = () => {
    if (keywordInput.trim() && !keywords.includes(keywordInput.trim())) {
      const newKeywords = [...keywords, keywordInput.trim()];
      setKeywords(newKeywords);
      setKeywordInput('');
      
      // If meetingId exists, update via API; otherwise just notify parent
      if (meetingId) {
        updateKeywords(newKeywords);
      } else {
        onKeywordsUpdated(newKeywords);
      }
    }
  };

  const removeKeyword = (keywordToRemove: string) => {
    const newKeywords = keywords.filter(keyword => keyword !== keywordToRemove);
    setKeywords(newKeywords);
    
    // If meetingId exists, update via API; otherwise just notify parent
    if (meetingId) {
      updateKeywords(newKeywords);
    } else {
      onKeywordsUpdated(newKeywords);
    }
  };

  const updateKeywords = async (newKeywords: string[]) => {
    if (!meetingId) return;
    
    setLoading(true);
    try {
      await meetingApi.updateKeywords(meetingId, newKeywords);
      onKeywordsUpdated(newKeywords);
    } catch (error) {
      console.error('Failed to update keywords:', error);
      setKeywords(currentKeywords);
      alert('Failed to update keywords');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addKeyword();
    }
  };

  return (
    <div className="keywords-manager">
      {showTitle && <h4>Keywords</h4>}

      <div className="keywords-input-wrapper">
        <input
          type="text"
          className="keywords-input"
          value={keywordInput}
          onChange={(e) => setKeywordInput(e.target.value)}
          onKeyDown={handleKeyPress}
          placeholder="Add keyword and press Enter"
          disabled={loading || disabled}
        />
        <button
          type="button"
          className="keywords-add-button"
          onClick={addKeyword}
          disabled={loading || disabled || !keywordInput.trim()}
        >
          Add
        </button>
      </div>

      <div className="keywords-list">
        {keywords.map((keyword) => (
          <span key={keyword} className="keyword-tag">
            {keyword}
            <button
              type="button"
              className="keyword-remove-button"
              onClick={() => removeKeyword(keyword)}
              disabled={loading || disabled}
            >
              ×
            </button>
          </span>
        ))}
      </div>

      {loading && <div className="loading-indicator">Updating keywords...</div>}
    </div>
  );
}