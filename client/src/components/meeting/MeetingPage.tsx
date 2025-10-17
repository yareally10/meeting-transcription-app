import React, { useState } from 'react';
import { Page, Dialog } from '../core';
import MeetingList from './MeetingList';
import MeetingListControls from './MeetingListControls';
import MeetingForm from './MeetingForm';
import MeetingDetails from './MeetingDetails';
import './MeetingPage.css';

const MeetingPage: React.FC = () => {
  const [selectedMeeting, setSelectedMeeting] = useState<string | null>(null);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const handleCreateClick = () => {
    setIsCreateDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setIsCreateDialogOpen(false);
  };

  const handleMeetingCreated = () => {
    setIsCreateDialogOpen(false);
    // TODO: Instead of reload, refresh the meeting list
    window.location.reload();
  };

  const handleSearch = (query: string) => {
    setSearchQuery(query);
  };

  return (
    <Page title="Meeting Transcription App">
      <div className="meeting-page-container">
        <div className="meeting-page-sidebar">
          <div className="meeting-list-header">
            <h2>Meetings</h2>
          </div>
          <MeetingListControls
            onSearch={handleSearch}
            onCreateClick={handleCreateClick}
          />
          <MeetingList
            onSelectMeeting={setSelectedMeeting}
            searchQuery={searchQuery}
          />
        </div>

        <div className="meeting-page-content">
          {selectedMeeting ? (
            <MeetingDetails meetingId={selectedMeeting} />
          ) : (
            <MeetingDetails meetingId="" />
          )}
        </div>
      </div>

      <Dialog
        isOpen={isCreateDialogOpen}
        onClose={handleCloseDialog}
        title="Create New Meeting"
      >
        <MeetingForm onMeetingCreated={handleMeetingCreated} />
      </Dialog>
    </Page>
  );
};

export default MeetingPage;
