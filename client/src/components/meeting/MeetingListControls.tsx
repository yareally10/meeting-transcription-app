import React, { useState, useEffect, useRef } from 'react';
import './MeetingListControls.css';

interface MeetingListControlsProps {
  onSearch: (query: string) => void;
  onCreateClick: () => void;
}

const MeetingListControls: React.FC<MeetingListControlsProps> = ({
  onSearch,
  onCreateClick
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const debounceTimer = useRef<number | null>(null);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
    };
  }, []);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchQuery(value);

    // Clear existing timer
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    // Set new timer - call onSearch after 300ms of no typing
    debounceTimer.current = setTimeout(() => {
      onSearch(value);
    }, 300);
  };

  const handleClearSearch = () => {
    setSearchQuery('');

    // Clear debounce timer
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    // Immediately clear search
    onSearch('');
  };

  return (
    <div className="meeting-list-controls">
      <div className="search-input-wrapper">
        <input
          type="text"
          className="search-input"
          placeholder="Search meetings..."
          value={searchQuery}
          onChange={handleSearchChange}
        />
        {searchQuery && (
          <button
            type="button"
            className="search-clear-button"
            onClick={handleClearSearch}
            aria-label="Clear search"
          >
            ×
          </button>
        )}
      </div>
      <button className="create-meeting-button" onClick={onCreateClick}>
        Create Meeting
      </button>
    </div>
  );
};

export default MeetingListControls;
