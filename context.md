# Meeting Transcription Platform - Architecture Context

## Project Overview
Building a comprehensive meeting transcription platform that allows users to create meetings, record audio with intelligent silence detection, and receive real-time transcriptions with keyword management. The system uses a microservices architecture with clear separation of concerns, Redis-backed job queue, and database access control.

## Architecture Pattern
**5-Container Microservices Architecture with Client-Side Silence Detection:**
- **Client Container**: React frontend with intelligent silence detection
- **Web Server Container**: Backend API with exclusive MongoDB access
- **Transcription Service Container**: Stateless audio processing service with Redis queue
- **MongoDB Container**: Centralized data persistence
- **Redis Container**: Job queue and session management with AOF persistence

## System Flow
```
Client (Silence Detection) → WebSocket → Web Server → Redis Queue → Transcription Workers → OpenAI Whisper
                                            ↓
                                        MongoDB
```

**Key Innovation**: Client-side silence detection creates complete, valid WebM audio chunks only when speech is detected, eliminating server-side audio processing and reducing transcription costs by 40-60%.

## Service Components

### 1. Client Container (Frontend)
- **Technology**: React 18 + Vite + TypeScript with Web Audio API
- **Port**: 3000
- **Responsibilities**:
  - Meeting creation and management interface
  - **Silence Detection** - Real-time speech detection using AnalyserNode
  - **Dynamic audio chunking** - Creates complete WebM chunks only when speech detected
  - **Silence filtering** - Automatically skips silent periods to reduce API costs
  - Real-time transcription progress display via WebSocket
  - Keyword management UI with live highlighting
  - Meeting dashboard and history views

**Silence Detection Features:**
- State machine: `waiting → recording → confirming_end`
- Configurable thresholds (silence detection, min/max chunk duration)
- Real-time volume visualization
- Each chunk is a valid, standalone WebM file

### 2. Web Server Container (Backend API)
- **Technology**: FastAPI with MongoDB integration
- **Port**: 8000
- **Responsibilities**:
  - **EXCLUSIVE MongoDB access** - only service that can read/write database
  - Meeting CRUD API endpoints
  - **WebSocket audio streaming** - Receives audio chunks via WebSocket
  - **Audio file management** - Organized storage in `volumes/shared_audio/{meeting_id}/audio/`
  - **Session management** - Unique session IDs per WebSocket connection
  - Forward audio chunks to Transcription Service
  - Receive webhook results from Transcription Service
  - Save transcription results to MongoDB
  - WebSocket management for real-time client updates

**File Management Structure:**
```
volumes/
├── mongodb/              # MongoDB persistent data
├── redis/                # Redis persistent data (AOF)
└── shared_audio/
    └── {meeting_id}/
        └── audio/
            └── audio_chunk_{session_id}_{counter}_{timestamp}.webm
```

**Audio Service:**
- Simple file storage service (`audio_service.py`)
- Generates filenames with session ID, counter, and timestamp
- Tracks chunk counters per session
- Cleanup on WebSocket disconnect

**Meeting State Management:**
- Status transitions: `created → transcribing → completed/failed`
- Real-time updates via WebSocket

### 3. Transcription Service Container
- **Technology**: FastAPI with Redis-backed job queue
- **Port**: 8001
- **Responsibilities**:
  - **STATELESS processing service** - no database access
  - **Redis-backed job queue** with persistence
  - OpenAI Whisper API integration
  - Multi-worker thread management (configurable, default: 3)
  - Webhook delivery to Web Server with results
  - Job status tracking with 24-hour TTL
  - **NO knowledge of meetings or persistent data**

**Modular Design:**
- `config.py` - Configuration with Redis URL
- `job_manager.py` - Redis queue and job status management
- `redis_queue.py` - Redis queue operations (BLPOP, RPUSH)
- `transcription_worker.py` - Worker threads for processing
- `webhook_handler.py` - Webhook delivery system

**Queue Features:**
- Redis BLPOP for efficient job dequeuing
- Job status stored in Redis with 24-hour TTL
- Persistent queue survives service restarts
- Worker threads pull from shared Redis queue

### 4. MongoDB Container
- **Technology**: MongoDB 7.0
- **Port**: 27017
- **Data Location**: `volumes/mongodb/`
- **Responsibilities**:
  - Meeting metadata persistence
  - Transcription result storage (full_transcription field)
  - Keyword management

### 5. Redis Container
- **Technology**: Redis 7 Alpine
- **Port**: 6379
- **Data Location**: `volumes/redis/`
- **Persistence**: AOF (Append-Only File) enabled
- **Responsibilities**:
  - Job queue for transcription tasks
  - Job status tracking (24-hour TTL)
  - Session counter management

## Critical Architecture Rules

### Database Access Control
- **ONLY Web Server** can connect to MongoDB
- **Transcription Service** has NO database access or knowledge
- **Client** accesses data only through Web Server APIs
- All database operations must be implemented in Web Server

### Service Communication Patterns
- **Client → Web Server**: HTTP REST APIs + WebSocket
- **Web Server → Transcription Service**: HTTP POST (submit jobs)
- **Transcription Service → Redis**: Job queue operations
- **Transcription Service → Web Server**: HTTP POST webhooks (results)
- **Web Server → MongoDB**: Direct database operations

### CORS Security
- **Web Server**: Allows only client origin (http://localhost:3000)
- **Transcription Service**: Allows only web server origin (http://web-server:8000)

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
  metadata: {
    language: String,
    participants: [String],
    totalDuration: Number,
    processingStarted: Date,
    processingCompleted: Date,
    totalProcessingTime: Number
  }
}
```

### Redis Job Data
```javascript
// Job Queue (List)
{
  job_id: String,
  meeting_id: String,
  filename: String,
  webhook_url: String
}

// Job Status (String with 24h TTL)
{
  job_id: String,
  status: String, // "queued", "processing", "completed", "failed"
  meeting_id: String,
  filename: String,
  created_at: ISO8601,
  completed_at: ISO8601,
  error_message: String
}
```

## Communication Flows

### Meeting Creation Flow
1. **Client** → **Web Server** POST `/meetings` (title, description, keywords)
2. **Web Server** → **MongoDB**: Insert new meeting document
3. **Web Server** → **Client**: Return meeting ID and details

### Audio Upload & Transcription Flow
1. **Client** detects speech → creates complete WebM chunk
2. **Client** → **Web Server** WebSocket `/ws/meeting/{id}/audio` (binary WebM data)
3. **Web Server** `audio_service`:
   - Generate filename with session ID, counter, timestamp
   - Save to `volumes/shared_audio/{meeting_id}/audio/audio_chunk_{session_id}_{counter}_{timestamp}.webm`
   - Return filename and metadata
4. **Web Server** → **Transcription Service** POST `/transcribe` (meeting_id, filename, webhook_url)
5. **Transcription Service**:
   - Create job in Redis with status "queued"
   - Enqueue job to Redis list
   - Return job ID (202 Accepted)
6. **Worker Thread**:
   - Dequeue job from Redis (BLPOP)
   - Update status to "processing"
   - Read audio file from shared volume
   - Call OpenAI Whisper API
   - Update job status in Redis
7. **Transcription Service** → **Web Server**: POST `/webhook/transcription-completed` (results)
8. **Web Server**:
   - Append transcription text to `meeting.fullTranscription` in MongoDB
   - Update meeting metadata
9. **Web Server** → **Client**: Real-time update via WebSocket with transcription text

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
- `WebSocket /ws/meeting/{id}/audio` - Audio streaming + real-time updates
- `POST /webhook/transcription-completed` - Receive transcription results
- `GET /transcription/health` - Check transcription service health
- `GET /transcription/job/{job_id}` - Get transcription job status (proxied)

### Transcription Service API Endpoints
- `POST /transcribe` - Accept audio chunk for processing
- `GET /job/{job_id}` - Check job status from Redis
- `GET /health` - Service health and queue size
- `GET /stats` - Processing statistics from Redis

## Technology Stack
- **Frontend**: React 18 + Vite + TypeScript with Web Audio API
- **Backend API**: FastAPI with async/await patterns using Motor MongoDB driver
- **Database**: MongoDB 7.0 with async pymongo/motor driver
- **Queue**: Redis 7 with AOF persistence
- **Transcription**: FastAPI with OpenAI Whisper API integration
- **Worker Management**: Threading-based workers pulling from Redis queue
- **Communication**: HTTP REST APIs, WebSocket, HTTP webhooks
- **Containerization**: Docker + Docker Compose with health checks and restart policies
- **File Storage**: Shared volume (`volumes/shared_audio/`) between web-server and transcription services

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
REDIS_URL=redis://redis:6379

# Client
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000

# MongoDB
MONGO_INITDB_DATABASE=meeting_db
```

## File Structure
```
project/
├── client/                      # React frontend (Vite + TypeScript)
│   ├── src/
│   │   ├── components/          # React components
│   │   ├── services/api.ts      # API client
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── Dockerfile
│   ├── .dockerignore
│   └── package.json
├── web-server/                  # FastAPI web server (Python)
│   ├── main.py                  # FastAPI app with WebSocket
│   ├── services.py              # Business logic
│   ├── audio_service.py         # Audio file storage
│   ├── transcription_service.py # HTTP client for transcription service
│   ├── websocket_manager.py     # WebSocket connections
│   ├── database.py              # MongoDB connection
│   ├── models.py                # Pydantic models
│   ├── config.py                # Configuration
│   ├── Dockerfile
│   ├── .dockerignore
│   └── requirements.txt
├── transcription/               # Transcription service (Python)
│   ├── main.py                  # FastAPI service
│   ├── config.py                # Configuration with Redis URL
│   ├── job_manager.py           # Redis queue and job status
│   ├── redis_queue.py           # Redis queue operations
│   ├── transcription_worker.py  # Worker threads
│   ├── webhook_handler.py       # Webhook delivery
│   ├── Dockerfile
│   ├── .dockerignore
│   └── requirements.txt
├── mongodb/                     # MongoDB initialization
│   └── init-mongo.js
├── volumes/                     # Persistent data (gitignored)
│   ├── mongodb/                 # MongoDB data
│   ├── redis/                   # Redis AOF data
│   └── shared_audio/            # Audio files by meeting
│       └── {meeting_id}/audio/
├── docker-compose.yml           # 5 services with health checks
├── .env.example
├── .gitignore
└── README.md
```

## Docker Configuration

### Health Checks
- **MongoDB**: `mongosh --eval "db.adminCommand('ping')"`
- **Redis**: `redis-cli ping`
- **Web Server**: `curl -f http://localhost:8000/`
- **Transcription**: `curl -f http://localhost:8001/health`
- **Restart Policy**: `unless-stopped` for all services

### Service Dependencies
- Client depends on: web-server (healthy)
- Web Server depends on: mongodb (healthy), transcription (started)
- Transcription depends on: redis (healthy)

## Key Development Principles

### Database Access Control
- **All MongoDB operations must be in Web Server service only**
- Transcription Service sends data via webhooks, never directly to database
- Client gets all data through Web Server APIs
- Single source of truth for all persistent data

### Service Independence
- Each service can be developed and tested independently
- Transcription Service is purely functional (Redis → processing → webhook)
- Web Server handles all business logic and data relationships
- Client focuses purely on UI/UX with no business logic

### Queue Management
- Redis provides persistent, distributed queue
- Jobs survive service restarts
- Multiple workers can process concurrently
- Job status tracked with TTL for automatic cleanup

### File Management Strategy
- Organized directory structure: `volumes/shared_audio/{meeting_id}/audio/`
- Session IDs prevent conflicts in concurrent WebSocket connections
- File naming: `audio_chunk_{session_id}_{counter}_{timestamp}.webm`
- Audio service manages counters and cleanup

### Error Handling Strategy
- Web Server handles all business logic errors and validation
- Transcription Service reports processing errors via webhook
- Client displays user-friendly error messages from Web Server
- Database errors contained within Web Server service
- Redis connection failures logged and retried

## Implementation Features

### Web Server Features
- **Complete MongoDB integration** using Motor async driver
- **Meeting CRUD operations** with proper ObjectId handling
- **WebSocket connection management** for real-time updates
- **Simplified audio service** - file storage only
- **Session-based file naming** with automatic counter management
- **Transcription service communication** via HTTP
- **Webhook handlers** for receiving results
- **CORS middleware** restricted to client origin
- **Lifespan management** for startup/shutdown

### Transcription Service Features
- **Redis-backed job queue** with persistence
- **Job status tracking** with 24-hour TTL
- **Configurable concurrent workers** (default: 3)
- **OpenAI Whisper integration**
- **Webhook delivery system** with retry logic
- **Health check endpoints** with queue size
- **Stateless design** - no local state
- **CORS restricted** to web server only

### Client Application Features
- **Meeting management UI** with full CRUD
- **Silence detection** with volume visualization
- **Dynamic audio chunking** - only speech sent
- **Real-time transcription display** via WebSocket
- **Keyword management** with live highlighting
- **Meeting list and details views**
- **Responsive React components** with TypeScript
