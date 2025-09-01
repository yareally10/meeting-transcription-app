import { useState } from 'react'
import MeetingList from './components/MeetingList'
import MeetingForm from './components/MeetingForm'
import MeetingDetails from './components/MeetingDetails'
import './App.css'

function App() {
  const [selectedMeeting, setSelectedMeeting] = useState<string | null>(null)

  return (
    <div className="App">
      <h1>Meeting Transcription Platform</h1>
      <div className="container">
        <div className="sidebar">
          <MeetingForm onMeetingCreated={() => window.location.reload()} />
          <MeetingList onSelectMeeting={setSelectedMeeting} />
        </div>
        <div className="main-content">
          {selectedMeeting ? (
            <MeetingDetails meetingId={selectedMeeting} />
          ) : (
            <MeetingDetails meetingId="" />
          )}
        </div>
      </div>
    </div>
  )
}

export default App