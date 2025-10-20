import React from 'react';
import { Meeting } from '../../types';
import './MeetingCard.css';

interface MeetingCardProps {
  meeting: Meeting;
  isSelected: boolean;
  onSelect: (meeting: Meeting) => void;
  onJoin: (meeting: Meeting) => void;
  onDelete: (id: string) => void;
}

const MeetingCard: React.FC<MeetingCardProps> = ({
  meeting,
  isSelected,
  onSelect,
  onJoin,
  onDelete
}) => {
  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm(`Are you sure you want to delete "${meeting.title}"?`)) {
      onDelete(meeting.id);
    }
  };

  const handleJoin = (e: React.MouseEvent) => {
    e.stopPropagation();
    onJoin(meeting);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return '#4CAF50';
      case 'transcribing':
        return '#2196F3';
      case 'uploading':
        return '#FF9800';
      case 'failed':
        return '#f44336';
      default:
        return '#9e9e9e';
    }
  };

  const getStatusLabel = (status: string) => {
    return status.charAt(0).toUpperCase() + status.slice(1);
  };

  return (
    <div
      className={`meeting-card ${isSelected ? 'meeting-card-selected' : ''}`}
      onClick={() => onSelect(meeting)}
    >
      <div className="meeting-card-header">
        <h3 className="meeting-card-title">{meeting.title}</h3>
        <button
          className="meeting-card-delete"
          onClick={handleDelete}
          aria-label="Delete meeting"
        >
          ×
        </button>
      </div>

      {meeting.description && (
        <p className="meeting-card-description">{meeting.description}</p>
      )}

      <div className="meeting-card-meta">
        <span
          className="meeting-card-status"
          style={{
            backgroundColor: `${getStatusColor(meeting.status)}15`,
            color: getStatusColor(meeting.status),
            borderColor: getStatusColor(meeting.status)
          }}
        >
          {getStatusLabel(meeting.status)}
        </span>
        <span className="meeting-card-date">
          {formatDate(meeting.createdAt)}
        </span>
        <button
          className="meeting-card-join-button"
          onClick={handleJoin}
          aria-label="Join meeting"
        >
          Join
        </button>
      </div>

      {meeting.keywords.length > 0 && (
        <div className="meeting-card-keywords">
          {meeting.keywords.map((keyword, index) => (
            <span key={index} className="meeting-card-keyword">
              {keyword}
            </span>
          ))}
        </div>
      )}

      {meeting.metadata?.totalDuration && (
        <div className="meeting-card-duration">
          Duration: {Math.round(meeting.metadata.totalDuration / 1000 / 60)}m
        </div>
      )}
    </div>
  );
};

export default MeetingCard;
