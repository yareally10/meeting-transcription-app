import { useMeetingContext } from '../../contexts/MeetingContext';
import { Meeting } from '../../types';
import MeetingCard from './MeetingCard';
import { List } from '../core';

interface MeetingListProps {
  searchQuery?: string;
  onRequestConfirmation: () => Promise<boolean>;
}

export default function MeetingList({ searchQuery = '', onRequestConfirmation }: MeetingListProps) {
  const {
    meetings,
    currentMeetingId,
    isInActiveMeeting,
    selectMeeting,
    joinMeeting,
    deleteMeeting,
    isLoading
  } = useMeetingContext();

  const handleSelectMeeting = async (meeting: Meeting) => {
    // Check if we need confirmation before switching
    if (isInActiveMeeting) {
      const confirmed = await onRequestConfirmation();
      if (!confirmed) return; // User cancelled
    }

    await selectMeeting(meeting.id);
  };

  const handleJoinMeeting = async (meeting: Meeting) => {
    // Check if we need confirmation before switching
    if (isInActiveMeeting && currentMeetingId !== meeting.id) {
      const confirmed = await onRequestConfirmation();
      if (!confirmed) return; // User cancelled
    }

    await joinMeeting(meeting.id);
  };

  const handleDeleteMeeting = async (meetingId: string) => {
    try {
      await deleteMeeting(meetingId);
    } catch (error) {
      console.error('Failed to delete meeting:', error);
      alert('Failed to delete meeting');
    }
  };

  if (isLoading) {
    return <div>Loading meetings...</div>;
  }

  // Filter meetings based on search query (case-insensitive)
  const filteredMeetings = meetings.filter((meeting) => {
    if (!searchQuery) return true;

    const query = searchQuery.toLowerCase();
    return (
      meeting.title.toLowerCase().includes(query) ||
      meeting.description.toLowerCase().includes(query)
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
              isSelected={currentMeetingId === meeting.id}
              onClick={() => handleSelectMeeting(meeting)}
            >
              <MeetingCard
                meeting={meeting}
                isSelected={currentMeetingId === meeting.id}
                onSelect={handleSelectMeeting}
                onJoin={handleJoinMeeting}
                onDelete={handleDeleteMeeting}
              />
            </List.Item>
          ))}
        </List>
      )}
    </div>
  );
}