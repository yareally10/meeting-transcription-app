import React, { useState, useEffect, useCallback } from 'react';
import { Page, Dialog } from '../core';
import MeetingList from './MeetingList';
import MeetingForm from './MeetingForm';
import MeetingDetails from './MeetingDetails';
import { MeetingProvider, useMeetingContext } from '../../contexts/MeetingContext';
import './MeetingPage.css';

const MeetingPageContent: React.FC = () => {
  const {
    currentMeetingId,
    currentMeetingMode,
    refreshMeetings,
    joinMeeting,
  } = useMeetingContext();

  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);

  // Confirmation dialog state
  const [isConfirmDialogOpen, setIsConfirmDialogOpen] = useState(false);
  const [confirmResolve, setConfirmResolve] = useState<((value: boolean) => void) | null>(null);

  // Load meetings on mount
  useEffect(() => {
    refreshMeetings();
  }, [refreshMeetings]);

  // Simplified confirmation handler with single message
  const requestConfirmation = useCallback((): Promise<boolean> => {
    return new Promise((resolve) => {
      setConfirmResolve(() => resolve);
      setIsConfirmDialogOpen(true);
    });
  }, []);

  const handleCreateClick = () => {
    setIsCreateDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setIsCreateDialogOpen(false);
  };

  const handleMeetingCreated = async (meeting: any) => {
    setIsCreateDialogOpen(false);
    // Auto-join the newly created meeting
    await joinMeeting(meeting.id);
  };

  const handleConfirmLeave = () => {
    if (confirmResolve) {
      confirmResolve(true);
    }
    setIsConfirmDialogOpen(false);
    setConfirmResolve(null);
  };

  const handleCancelLeave = () => {
    if (confirmResolve) {
      confirmResolve(false);
    }
    setIsConfirmDialogOpen(false);
    setConfirmResolve(null);
  };

  return (
    <Page title="Meeting Transcription App">
      <div className="meeting-page-container">
        <div className="meeting-page-sidebar">
          <MeetingList
            onRequestConfirmation={requestConfirmation}
            onCreateClick={handleCreateClick}
          />
        </div>

        <div className="meeting-page-content">
          {currentMeetingId ? (
            <MeetingDetails meetingId={currentMeetingId} mode={currentMeetingMode} />
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
          <p>You are currently in a meeting. Do you want to leave?</p>
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

const MeetingPage: React.FC = () => {
  return (
    <MeetingProvider>
      <MeetingPageContent />
    </MeetingProvider>
  );
};

export default MeetingPage;
