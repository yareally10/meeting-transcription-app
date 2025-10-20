import React, { useState } from 'react';
import { Page, Dialog } from '../core';
import MeetingList from './MeetingList';
import MeetingListControls from './MeetingListControls';
import MeetingForm from './MeetingForm';
import MeetingDetails from './MeetingDetails';
import './MeetingPage.css';

const MeetingPage: React.FC = () => {
  const [selectedMeeting, setSelectedMeeting] = useState<string | null>(null);
  const [meetingMode, setMeetingMode] = useState<'view' | 'join'>('view');
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Confirmation dialog state
  const [isConfirmDialogOpen, setIsConfirmDialogOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState<{
    type: 'select' | 'join';
    meetingId: string;
    message: string;
  } | null>(null);

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

  const handleSelectMeeting = (meetingId: string) => {
    // If currently in a joined meeting and trying to switch to a different meeting
    if (meetingMode === 'join' && selectedMeeting && selectedMeeting !== meetingId) {
      setConfirmAction({
        type: 'select',
        meetingId,
        message: 'You are currently in a meeting. Are you sure you want to leave and view another meeting?'
      });
      setIsConfirmDialogOpen(true);
      return;
    }

    setSelectedMeeting(meetingId);
    setMeetingMode('view');
  };

  const handleJoinMeeting = (meetingId: string) => {
    // If currently in a joined meeting and trying to join a different meeting
    if (meetingMode === 'join' && selectedMeeting && selectedMeeting !== meetingId) {
      setConfirmAction({
        type: 'join',
        meetingId,
        message: 'You are currently in a meeting. Are you sure you want to leave and join another meeting?'
      });
      setIsConfirmDialogOpen(true);
      return;
    }

    setSelectedMeeting(meetingId);
    setMeetingMode('join');
  };

  const handleConfirmLeave = () => {
    if (confirmAction) {
      setSelectedMeeting(confirmAction.meetingId);
      setMeetingMode(confirmAction.type === 'join' ? 'join' : 'view');
    }
    setIsConfirmDialogOpen(false);
    setConfirmAction(null);
  };

  const handleCancelLeave = () => {
    setIsConfirmDialogOpen(false);
    setConfirmAction(null);
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
            onSelectMeeting={handleSelectMeeting}
            onJoinMeeting={handleJoinMeeting}
            searchQuery={searchQuery}
          />
        </div>

        <div className="meeting-page-content">
          {selectedMeeting ? (
            <MeetingDetails meetingId={selectedMeeting} mode={meetingMode} />
          ) : (
            <MeetingDetails meetingId="" mode="view" />
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

      <Dialog
        isOpen={isConfirmDialogOpen}
        onClose={handleCancelLeave}
        title="Leave Meeting?"
      >
        <div className="confirm-dialog-content">
          <p>{confirmAction?.message}</p>
          <div className="confirm-dialog-actions">
            <button
              className="confirm-dialog-button confirm-dialog-button-cancel"
              onClick={handleCancelLeave}
            >
              Cancel
            </button>
            <button
              className="confirm-dialog-button confirm-dialog-button-confirm"
              onClick={handleConfirmLeave}
            >
              Leave Meeting
            </button>
          </div>
        </div>
      </Dialog>
    </Page>
  );
};

export default MeetingPage;
