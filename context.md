# Meeting Transcription Platform - Architecture Context

## Project Overview
Building a comprehensive meeting transcription platform that allows users to create meetings, record audio with intelligent Voice Activity Detection (VAD), and receive real-time transcriptions with keyword management. The system uses a microservices architecture with clear separation of concerns and database access control.

## Architecture Pattern
**4-Container Microservices Architecture with Client-Side VAD:**
- **Client Container**: React frontend with intelligent Voice Activity Detection
- **Web Server Container**: Backend API with exclusive MongoDB access
- **Transcription Service Container**: Stateless audio processing service
- **MongoDB Container**: Centralized data persistence

## System Flow
```
Client (VAD) → WebSocket → Web Server → Transcription Service → OpenAI Whisper
                              ↓
                          MongoDB
```

**Key Innovation**: Client-side Voice Activity Detection creates complete, valid WebM audio chunks only when speech is detected, eliminating server-side audio processing and reducing transcription costs by 40-60%.

## Service Components

### 1. Client Container (Frontend)
- **Technology**: React 18 + Vite + TypeScript with Web Audio API
- **Port**: 3000
- **Responsibilities**:
  - Meeting creation and management interface
  - **Voice Activity Detection (VAD)** - Real-time speech detection using AnalyserNode
  - **Dynamic audio chunking** - Creates complete WebM chunks only when speech detected
  - **Silence filtering** - Automatically skips silent periods to reduce API costs
  - Real-time transcription progress display via WebSocket
  - Keyword management UI with live highlighting
  - Meeting dashboard and history views

**VAD Features:**
- State machine: `waiting → recording → confirming_end`
- Configurable thresholds (silence detection, min/max chunk duration)
- Real-time volume visualization
- Each chunk is a valid, standalone WebM file (solves header corruption issue)

### 2. Web Server Container (Backend API)
- **Technology**: FastAPI with MongoDB integration
- **Port**: 8000
- **Responsibilities**:
  - **EXCLUSIVE MongoDB access** - only service that can read/write database
  - Meeting CRUD API endpoints
  - **WebSocket audio streaming** - Receives VAD chunks via WebSocket
  - **File management** - Organized storage structure per meeting
  - **Session management** - Unique session IDs prevent conflicts in multi-user meetings
  - Forward audio chunks to Transcription Service
  - Receive webhook results from Transcription Service
  - Save transcription results to both MongoDB and file system
  - WebSocket management for real-time client updates

**File Management Structure:**
```
shared_audio/
└── {meeting_id}/
    ├── audios/
    │   └── vad_{session_id}_{counter}_{timestamp}.webm
    └── transcriptions/
        └── vad_{session_id}_{counter}_{timestamp}.txt
```

**Meeting State Management:**
- Track chunk count and transcription progress
- Status transitions: `created → transcribing → completed/failed`
- Only mark "completed" when all submitted chunks have been transcribed
- Persist state across WebSocket disconnections
- Handle out-of-order transcription completion

**Simplified Architecture:**
- ✅ No server-side audio aggregation (VAD chunks are already complete)
- ✅ No audio slicing/processing (eliminated `audio_service.py`)
- ✅ Direct WebSocket → File Save → Transcription pipeline

### 3. Transcription Service Container
- **Technology**: FastAPI with internal queue management
- **Port**: 8001
- **Responsibilities**:
  - **STATELESS processing service** - no database access
  - Internal queue management (threading-based, no Redis for simplicity)
  - Audio processing and optimization
  - OpenAI Whisper API integration
  - Background worker thread management
  - Webhook delivery to Web Server with results
  - **NO knowledge of meetings or persistent data**

### 4. MongoDB Container
- **Technology**: MongoDB
- **Port**: 27017
- **Responsibilities**:
  - Meeting metadata persistence
  - Transcription result storage (full_transcription field)
  - Keyword management

## Critical Architecture Rules

### Database Access Control
- **ONLY Web Server** can connect to MongoDB
- **Transcription Service** has NO database access or knowledge
- **Client** accesses data only through Web Server APIs
- All database operations must be implemented in Web Server

### Service Communication Patterns
- **Client → Web Server**: HTTP REST APIs + WebSocket
- **Web Server → Transcription Service**: HTTP POST (push transcription requests onto queue)
- **Transcription Service → Web Server**: HTTP POST webhooks (results)
- **Web Server → MongoDB**: Direct database operations

## Data Models

### Meeting Collection (MongoDB)
```javascript
{
  _id: ObjectId,
  title: String,
  description: String,
  createdAt: Date,
  updatedAt: Date,
  status: String, // "created", "transcribing", "completed", "failed"
  keywords: [String], // User-managed keywords
  fullTranscription: String, // Combined from all chunks
  totalChunks: Number, // Total chunks submitted
  completedChunks: Number // Chunks successfully transcribed
}
```

## Communication Flows

### Meeting Creation Flow
1. **Client** → **Web Server** POST `/meetings` (title, description, keywords)
2. **Web Server** → **MongoDB**: Insert new meeting document
3. **Web Server** → **Client**: Return meeting ID and details

### Audio Upload & Transcription Flow (VAD-Based)
1. **Client VAD** detects speech → creates complete WebM chunk
2. **Client** → **Web Server** WebSocket `/ws/meeting/{id}/audio` (binary WebM data)
3. **Web Server**:
   - Save audio to `shared_audio/{meeting_id}/audios/vad_{session_id}_{counter}_{timestamp}.webm`
   - Increment `totalChunks` in MongoDB
   - Update meeting status to "transcribing"
4. **Web Server** → **Transcription Service** POST `/transcribe` (filename + meeting_id + webhook_url)
5. **Transcription Service** → **Web Server**: Immediate response (202 Accepted, job ID)
6. **Transcription Service**: Background processing (internal queue with worker threads)
7. **Transcription Service** → **Web Server**: POST `/webhook/transcription-completed` (results)
8. **Web Server**:
   - Save transcription to `shared_audio/{meeting_id}/transcriptions/vad_{session_id}_{counter}_{timestamp}.txt`
   - Append transcription text to `meeting.fullTranscription` in MongoDB
   - Increment `completedChunks` in MongoDB
   - Check if `completedChunks == totalChunks` → set status to "completed"
9. **Web Server** → **Client**: Real-time update via WebSocket with transcription text

**Key Differences from Original:**
- ✅ Client creates chunks (not server)
- ✅ WebSocket streaming (not HTTP POST)
- ✅ No intermediate processing (direct save)
- ✅ Session ID prevents multi-user conflicts
- ✅ Dual storage: MongoDB + file system
- ✅ State tracking for accurate completion detection

### Keyword Management Flow
1. **Client** → **Web Server** PUT `/meetings/{id}/keywords` (keyword array)
2. **Web Server** → **MongoDB**: Update meeting keywords field
3. **Web Server** → **Client**: Updated meeting data

## API Endpoints Structure

### Web Server API Endpoints
- `POST /meetings` - Create new meeting
- `GET /meetings` - List all meetings
- `GET /meetings/{id}` - Get meeting details
- `PUT /meetings/{id}` - Update meeting metadata
- `DELETE /meetings/{id}` - Delete meeting
- `PUT /meetings/{id}/keywords` - Update keywords
- `WebSocket /ws/meeting/{id}/audio` - VAD audio streaming + real-time updates
- `POST /webhook/transcription-completed` - Receive transcription results
- `GET /transcription/health` - Check transcription service health
- `GET /transcription/job/{job_id}` - Get transcription job status

### Transcription Service API Endpoints
- `POST /transcribe` - Accept audio chunk for processing
- `GET /job/{internal_job_id}` - Check processing status
- `GET /health` - Service health check
- `GET /stats` - Processing statistics

## Technology Stack
- **Frontend**: React 18 + Vite + TypeScript with Web Audio API
- **Backend API**: FastAPI with async/await patterns using Motor MongoDB driver
- **Database**: MongoDB 7.0 with async pymongo/motor driver
- **Transcription**: FastAPI with OpenAI Whisper API integration
- **Queue**: Threading-based internal queue with job management (no external dependencies)
- **Communication**: HTTP REST APIs, WebSocket, HTTP webhooks
- **Containerization**: Docker + Docker Compose with multi-service orchestration
- **File Storage**: Shared volume for audio files and transcriptions between web-server and transcription services

## Environment Configuration
```bash
# Web Server
MONGODB_URL=mongodb://mongodb:27017
DATABASE_NAME=meeting_db
TRANSCRIPTION_SERVICE_URL=http://transcription:8001
WEB_SERVER_URL=http://web-server:8000

# Transcription Service
WEB_SERVER_URL=http://web-server:8000
OPENAI_API_KEY=your_openai_key
MAX_CONCURRENT_JOBS=3

# Client
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000

# MongoDB
MONGO_INITDB_DATABASE=meeting_db
```

## File Structure
```
project/
├── client/                      # React frontend application (Vite + TypeScript)
│   ├── src/
│   │   ├── components/          # React components
│   │   │   ├── AudioRecorder.tsx        # VAD audio recording
│   │   │   ├── KeywordsManager.tsx      # Keyword CRUD operations
│   │   │   ├── MeetingDetails.tsx       # Individual meeting view
│   │   │   ├── MeetingForm.tsx          # Meeting creation/editing
│   │   │   ├── MeetingList.tsx          # List all meetings
│   │   │   └── RealTimeTranscription.tsx # Live transcription display
│   │   ├── services/
│   │   │   ├── api.ts                   # API client
│   │   │   └── keywordMatcher.ts        # Keyword highlighting logic
│   │   ├── App.tsx              # Main application component
│   │   └── main.tsx             # Entry point
│   ├── package.json             # React dependencies
│   └── Dockerfile               # Client container build
├── web-server/                  # FastAPI web server (Python)
│   ├── main.py                  # FastAPI application with WebSocket endpoint
│   ├── services.py              # Business logic (MeetingService, TranscriptionWebhookService)
│   ├── transcription_service.py # Transcription service HTTP client
│   ├── websocket_manager.py     # WebSocket connection management
│   ├── database.py              # MongoDB connection
│   ├── models.py                # Pydantic models
│   ├── config.py                # Configuration
│   ├── requirements.txt         # Python dependencies
│   └── Dockerfile               # Web server container build
├── transcription/               # Transcription service (Python)
│   ├── main.py                  # FastAPI transcription service
│   ├── config.py                # Configuration management
│   ├── job_manager.py           # Internal job queue management
│   ├── transcription_worker.py  # Background worker threads
│   ├── webhook_handler.py       # Webhook delivery to web server
│   ├── requirements.txt         # Python dependencies
│   └── Dockerfile               # Transcription container build
├── mongodb/                     # MongoDB initialization
│   └── init-mongo.js           # Database initialization script
├── shared_audio/               # Shared volume for audio and transcription files
│   └── {meeting_id}/
│       ├── audios/             # WebM audio files
│       └── transcriptions/     # Text transcription files
├── docker-compose.yml          # All 4 services configuration
├── .env.example                # Environment variables template
└── README.md                   # Project documentation
```

## Key Development Principles

### Database Access Control
- **All MongoDB operations must be in Web Server service only**
- Transcription Service sends data via webhooks, never directly to database
- Client gets all data through Web Server APIs
- Single source of truth for all persistent data

### Service Independence
- Each service can be developed and tested independently
- Transcription Service is purely functional (input → processing → webhook output)
- Web Server handles all business logic and data relationships
- Client focuses purely on UI/UX with no business logic

### Error Handling Strategy
- Web Server handles all business logic errors and validation
- Transcription Service reports processing errors via webhook
- Client displays user-friendly error messages from Web Server
- Database errors contained within Web Server service

### File Management Strategy
- Organized directory structure per meeting
- Separate folders for audio and transcription files
- Session IDs prevent conflicts in multi-user scenarios
- File naming convention: `vad_{session_id}_{counter}_{timestamp}.{ext}`
- Dual persistence: MongoDB (aggregated) + File system (individual chunks)

## Implementation Features

### Web Server Features
- **Complete MongoDB integration** using Motor async driver
- **Meeting CRUD operations** with proper ObjectId handling
- **WebSocket connection management** for real-time updates
- **Dual file storage** - audio files + transcription text files
- **State tracking** - totalChunks and completedChunks for accurate status
- **Transcription service communication** via HTTP requests
- **Webhook handlers** for receiving transcription results
- **CORS middleware** configured for client communication
- **Lifespan management** for proper startup/shutdown

### Transcription Service Features
- **Job queue management** with threading-based workers
- **Configurable concurrent processing** (default: 3 workers)
- **OpenAI Whisper integration** for audio transcription
- **Webhook delivery system** to notify web server of completion
- **Health check endpoints** for monitoring
- **Error handling and retry logic** for failed jobs
- **Stateless design** with no database dependencies

### Client Application Features
- **Meeting management UI** with full CRUD operations
- **Voice Activity Detection** with real-time volume visualization
- **Dynamic audio chunking** - only sends speech, skips silence
- **Real-time transcription display** via WebSocket
- **Keyword management** with live highlighting in transcriptions
- **Meeting list and details views** with status tracking
- **Responsive React components** built with TypeScript
- **Axios integration** for API communication
