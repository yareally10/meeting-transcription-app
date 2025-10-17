import { useState, useEffect } from 'react';
import { meetingApi } from '../services/api';
import { Meeting } from '../types';
import MeetingCard from './MeetingCard';

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

  const handleSelectMeeting = (meeting: Meeting) => {
    setSelectedMeetingId(meeting.id);
    onSelectMeeting(meeting.id);
  };

  const handleDeleteMeeting = async (meetingId: string) => {
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
        <div className="meeting-list">
          {meetings.map((meeting) => (
            <MeetingCard
              key={meeting.id}
              meeting={meeting}
              isSelected={selectedMeetingId === meeting.id}
              onSelect={handleSelectMeeting}
              onDelete={handleDeleteMeeting}
            />
          ))}
        </div>
      )}
    </div>
  );
}