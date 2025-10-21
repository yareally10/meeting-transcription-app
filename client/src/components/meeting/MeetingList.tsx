import { useState } from 'react';
import { useMeetingContext } from '../../contexts/MeetingContext';
import { Meeting } from '../../types';
import MeetingCard from './MeetingCard';
import MeetingListControls from './MeetingListControls';
import { List } from '../core';
import './MeetingList.css';

interface MeetingListProps {
  onRequestConfirmation: () => Promise<boolean>;
  onCreateClick: () => void;
}

export default function MeetingList({ onRequestConfirmation, onCreateClick }: MeetingListProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const {
    meetings,
    currentMeetingId,
    isInActiveMeeting,
    selectMeeting,
    joinMeeting,
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

  const handleSearch = (query: string) => {
    setSearchQuery(query);
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
    <div className="meeting-list-container">
      <h1 className="meeting-list-title">
        {filteredMeetings.length === 1 ? 'Meeting' : 'Meetings'} [{filteredMeetings.length} / {meetings.length}] 
      </h1>

      <MeetingListControls
        onSearch={handleSearch}
        onCreateClick={onCreateClick}
      />

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
              />
            </List.Item>
          ))}
        </List>
      )}
    </div>
  );
}