import { useState, useEffect } from 'react';
import { meetingApi } from '../../services/api';
import { Meeting } from '../../types';
import MeetingCard from './MeetingCard';
import { List } from '../core';

interface MeetingListProps {
  onSelectMeeting: (meetingId: string) => void;
  searchQuery?: string;
}

export default function MeetingList({ onSelectMeeting, searchQuery = '' }: MeetingListProps) {
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

  // Filter meetings based on search query (case-insensitive)
  const filteredMeetings = meetings.filter((meeting) => {
    if (!searchQuery) return true;

    const query = searchQuery.toLowerCase();
    return (
      meeting.title.toLowerCase().includes(query) ||
      meeting.description.toLowerCase().includes(query) ||
      meeting.keywords.some(keyword => keyword.toLowerCase().includes(query))
    );
  });

  return (
    <div>
      <div className="meeting-list-count">
        {filteredMeetings.length} {filteredMeetings.length === 1 ? 'meeting' : 'meetings'}
        {searchQuery && filteredMeetings.length !== meetings.length && (
          <span className="meeting-list-count-total"> (of {meetings.length} total)</span>
        )}
      </div>
      {filteredMeetings.length === 0 ? (
        <p className="meeting-list-empty">
          {searchQuery
            ? `No meetings found matching "${searchQuery}".`
            : 'No meetings yet. Create your first meeting using the button above.'}
        </p>
      ) : (
        <List className="meeting-list">
          {filteredMeetings.map((meeting) => (
            <List.Item
              key={meeting.id}
              isSelected={selectedMeetingId === meeting.id}
              onClick={() => handleSelectMeeting(meeting)}
            >
              <MeetingCard
                meeting={meeting}
                isSelected={selectedMeetingId === meeting.id}
                onSelect={handleSelectMeeting}
                onDelete={handleDeleteMeeting}
              />
            </List.Item>
          ))}
        </List>
      )}
    </div>
  );
}