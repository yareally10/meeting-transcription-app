import { useState, useEffect } from 'react';
import { meetingApi } from '../services/api';
import { Meeting } from '../types';

interface MeetingListProps {
  onSelectMeeting: (meetingId: string) => void;
}

export default function MeetingList({ onSelectMeeting }: MeetingListProps) {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedMeetingId, setSelectedMeetingId] = useState<string | null>(null);

  useEffect(() => {
    loadMeetings();
  }, []);

  const loadMeetings = async () => {
    try {
      const data = await meetingApi.getAll();
      setMeetings(data);
    } catch (error) {
      console.error('Failed to load meetings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectMeeting = (meetingId: string) => {
    setSelectedMeetingId(meetingId);
    onSelectMeeting(meetingId);
  };

  const handleDeleteMeeting = async (meetingId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Are you sure you want to delete this meeting?')) {
      try {
        await meetingApi.delete(meetingId);
        setMeetings(meetings.filter(m => m.id !== meetingId));
        if (selectedMeetingId === meetingId) {
          setSelectedMeetingId(null);
          onSelectMeeting('');
        }
      } catch (error) {
        console.error('Failed to delete meeting:', error);
        alert('Failed to delete meeting');
      }
    }
  };

  if (loading) {
    return <div>Loading meetings...</div>;
  }

  return (
    <div>
      <h3>Meetings ({meetings.length})</h3>
      {meetings.length === 0 ? (
        <p>No meetings yet. Create your first meeting above.</p>
      ) : (
        <ul className="meeting-list">
          {meetings.map((meeting) => (
            <li
              key={meeting.id}
              className={`meeting-item ${selectedMeetingId === meeting.id ? 'selected' : ''}`}
              onClick={() => handleSelectMeeting(meeting.id)}
            >
              <div className="meeting-title">{meeting.title}</div>
              <div className="meeting-description">{meeting.description}</div>
              {meeting.keywords.length > 0 && (
                <div className="keywords-list">
                  {meeting.keywords.map((keyword) => (
                    <span key={keyword} className="keyword-tag">
                      {keyword}
                    </span>
                  ))}
                </div>
              )}
              <div className="meeting-actions">
                <button
                  onClick={(e) => handleDeleteMeeting(meeting.id, e)}
                  className="delete-btn"
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}