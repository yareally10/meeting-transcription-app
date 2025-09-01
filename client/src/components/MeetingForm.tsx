import { useState } from 'react';
import { meetingApi } from '../services/api';
import { CreateMeetingRequest } from '../types';

interface MeetingFormProps {
  onMeetingCreated: () => void;
}

export default function MeetingForm({ onMeetingCreated }: MeetingFormProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [keywords, setKeywords] = useState<string[]>([]);
  const [keywordInput, setKeywordInput] = useState('');
  const [loading, setLoading] = useState(false);

  const addKeyword = () => {
    if (keywordInput.trim() && !keywords.includes(keywordInput.trim())) {
      setKeywords([...keywords, keywordInput.trim()]);
      setKeywordInput('');
    }
  };

  const removeKeyword = (keyword: string) => {
    setKeywords(keywords.filter(k => k !== keyword));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    setLoading(true);
    try {
      const meetingData: CreateMeetingRequest = {
        title: title.trim(),
        description: description.trim(),
        keywords,
      };
      
      await meetingApi.create(meetingData);
      setTitle('');
      setDescription('');
      setKeywords([]);
      setKeywordInput('');
      onMeetingCreated();
    } catch (error) {
      console.error('Failed to create meeting:', error);
      alert('Failed to create meeting');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="meeting-form">
      <h3>Create New Meeting</h3>
      
      <div className="form-group">
        <label htmlFor="title">Title</label>
        <input
          id="title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Enter meeting title"
          required
        />
      </div>

      <div className="form-group">
        <label htmlFor="description">Description</label>
        <textarea
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Enter meeting description"
          rows={3}
        />
      </div>

      <div className="form-group">
        <label htmlFor="keywords">Keywords</label>
        <div className="keywords-input">
          <input
            id="keywords"
            type="text"
            value={keywordInput}
            onChange={(e) => setKeywordInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addKeyword())}
            placeholder="Add keyword and press Enter"
          />
          <button type="button" onClick={addKeyword}>Add</button>
        </div>
        <div className="keywords-list">
          {keywords.map((keyword) => (
            <span key={keyword} className="keyword-tag">
              {keyword}
              <button type="button" onClick={() => removeKeyword(keyword)}>×</button>
            </span>
          ))}
        </div>
      </div>

      <button type="submit" disabled={loading || !title.trim()}>
        {loading ? 'Creating...' : 'Create Meeting'}
      </button>
    </form>
  );
}