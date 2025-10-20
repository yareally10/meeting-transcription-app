import { useState } from 'react';
import { Meeting, CreateMeetingRequest } from '../../types';
import { useMeetingContext } from '../../contexts/MeetingContext';
import KeywordsManager from './KeywordsManager';

interface MeetingFormProps {
  onMeetingCreated: (meeting: Meeting) => void;
}

export default function MeetingForm({ onMeetingCreated }: MeetingFormProps) {
  const { createMeeting, isLoading, error } = useMeetingContext();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [keywords, setKeywords] = useState<string[]>([]);

  const handleKeywordsUpdated = (newKeywords: string[]) => {
    setKeywords(newKeywords);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    const meetingData: CreateMeetingRequest = {
      title: title.trim(),
      description: description.trim(),
      keywords,
    };

    const newMeeting = await createMeeting(meetingData);

    if (newMeeting) {
      // Clear form
      setTitle('');
      setDescription('');
      setKeywords([]);
      onMeetingCreated(newMeeting);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="meeting-form">
      <h3>Create New Meeting</h3>

      {error && (
        <div className="form-error" style={{ color: '#d32f2f', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

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
        <KeywordsManager
          currentKeywords={keywords}
          onKeywordsUpdated={handleKeywordsUpdated}
          disabled={isLoading}
          showTitle={false}
        />
      </div>

      <button type="submit" disabled={isLoading || !title.trim()}>
        {isLoading ? 'Creating...' : 'Create Meeting'}
      </button>
    </form>
  );
}