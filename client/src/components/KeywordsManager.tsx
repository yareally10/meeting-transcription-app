import { useState } from 'react';
import { meetingApi } from '../services/api';

interface KeywordsManagerProps {
  meetingId: string;
  currentKeywords: string[];
  onKeywordsUpdated: (keywords: string[]) => void;
}

export default function KeywordsManager({ meetingId, currentKeywords, onKeywordsUpdated }: KeywordsManagerProps) {
  const [keywords, setKeywords] = useState<string[]>(currentKeywords);
  const [keywordInput, setKeywordInput] = useState('');
  const [loading, setLoading] = useState(false);

  const addKeyword = () => {
    if (keywordInput.trim() && !keywords.includes(keywordInput.trim())) {
      const newKeywords = [...keywords, keywordInput.trim()];
      setKeywords(newKeywords);
      setKeywordInput('');
      updateKeywords(newKeywords);
    }
  };

  const removeKeyword = (keywordToRemove: string) => {
    const newKeywords = keywords.filter(keyword => keyword !== keywordToRemove);
    setKeywords(newKeywords);
    updateKeywords(newKeywords);
  };

  const updateKeywords = async (newKeywords: string[]) => {
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

  return (
    <div className="keywords-manager">
      <h4>Keywords</h4>
      
      <div className="keywords-input">
        <input
          type="text"
          value={keywordInput}
          onChange={(e) => setKeywordInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addKeyword())}
          placeholder="Add keyword and press Enter"
          disabled={loading}
        />
        <button type="button" onClick={addKeyword} disabled={loading || !keywordInput.trim()}>
          Add
        </button>
      </div>

      <div className="keywords-list">
        {keywords.map((keyword) => (
          <span key={keyword} className="keyword-tag">
            {keyword}
            <button 
              type="button" 
              onClick={() => removeKeyword(keyword)}
              disabled={loading}
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