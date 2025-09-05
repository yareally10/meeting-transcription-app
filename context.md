# Meeting Transcription Platform - Architecture Context

## Project Overview
Building a comprehensive meeting transcription platform that allows users to create meetings, upload audio files, and receive real-time transcriptions with keyword management. The system uses a microservices architecture with clear separation of concerns and database access control.

## Architecture Pattern
**4-Container Microservices Architecture with Controlled Database Access:**
- **Client Container**: Frontend UI for meeting management
- **Web Server Container**: Backend API with exclusive MongoDB access
- **Transcription Service Container**: Stateless audio processing service
- **MongoDB Container**: Centralized data persistence

## System Flow
```
Client ↔ Web Server ← Transcription Service → OpenAI Whisper
         ↓
      MongoDB
```

## Service Components

### 1. Client Container (Frontend)
- **Technology**: React, Vite
- **Port**: 3000
- **Responsibilities**:
  - Meeting creation and management interface
  - Audio file upload with chunking
  - Real-time transcription progress display
  - Keyword management UI (CRUD operations)
  - Meeting dashboard and history views
  - WebSocket connection for live updates

### 2. Web Server Container (Backend API)
- **Technology**: FastAPI with MongoDB integration
- **Port**: 8000
- **Responsibilities**:
  - **EXCLUSIVE MongoDB access** - only service that can read/write database
  - Meeting CRUD API endpoints
  - Audio chunk upload handling (saving audio files to shared volume with Transcription Service Container)
  - Forward audio chunks to Transcription Service
  - Receive webhook results from Transcription Service
  - Save transcription results to MongoDB
  - WebSocket management for real-time client updates

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
  - **NO knowledge of meetings, users, or persistent data**

### 4. MongoDB Container
- **Technology**: MongoDB
- **Port**: 27017
- **Responsibilities**:
  - Meeting metadata persistence
  - Transcription result storage
  - Keyword management
  - User data (not currently used)

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
  createdBy: String, // userId
  createdAt: Date,
  updatedAt: Date,
  status: String, // "created", "uploading", "transcribing", "completed", "failed"
  keywords: [String], // User-managed keywords
  fullTranscription: String, // Combined from all chunks
}
```

### Users Collection (MongoDB)
```javascript
{
  _id: ObjectId,
  email: String,
  name: String,
  createdAt: Date,
  lastLoginAt: Date,
  preferences: {
    defaultLanguage: String,
    notificationSettings: Object
  }
}
```

## Communication Flows

### Meeting Creation Flow
1. **Client** → **Web Server** POST `/meetings` (title, description, keywords)
2. **Web Server** → **MongoDB**: Insert new meeting document
3. **Web Server** → **Client**: Return meeting ID and details

### Audio Upload & Transcription Flow
1. **Client** → **Web Server** POST `/meetings/{id}/upload-chunk` (audio chunk)
2. **Web Server** → **MongoDB**: Update meeting status and chunk metadata
3. **Web Server** → **Transcription Service** POST `/transcribe` (audio chunk + metadata)
4. **Transcription Service** → **Web Server**: Immediate response (202 Accepted, internal job ID)
5. **Web Server** → **Client**: Upload confirmation via WebSocket
6. **Transcription Service**: Background processing (internal queue)
7. **Transcription Service** → **Web Server**: POST `/webhook/chunk-completed` (results)
8. **Web Server** → **MongoDB**: Save transcription results, update meeting status
9. **Web Server** → **Client**: Progress update via WebSocket

### Keyword Management Flow
1. **Client** → **Web Server** PUT `/meetings/{id}/keywords` (keyword array)
2. **Web Server** → **MongoDB**: Update meeting keywords field
3. **Web Server** → **Client**: Updated meeting data

## API Endpoints Structure

### Web Server API Endpoints
- `POST /meetings` - Create new meeting
- `GET /meetings` - List user's meetings
- `GET /meetings/{id}` - Get meeting details
- `PUT /meetings/{id}` - Update meeting metadata
- `DELETE /meetings/{id}` - Delete meeting
- `POST /meetings/{id}/upload-chunk` - Upload audio chunk
- `PUT /meetings/{id}/keywords` - Update keywords
- `WebSocket /ws/{user_id}` - Real-time updates
- `POST /webhook/chunk-completed` - Receive transcription results
- `POST /webhook/chunk-failed` - Handle transcription failures

### Transcription Service API Endpoints
- `POST /transcribe` - Accept audio chunk for processing
- `GET /job/{internal_job_id}` - Check processing status
- `GET /health` - Service health check
- `GET /stats` - Processing statistics

## Technology Stack
- **Frontend**: React/Next.js with real-time WebSocket support
- **Backend API**: FastAPI with async/await patterns
- **Database**: MongoDB with pymongo/motor async driver
- **Transcription**: FastAPI with OpenAI Whisper integration
- **Queue**: Threading-based internal queue (no external dependencies)
- **Communication**: HTTP REST APIs, WebSocket, HTTP webhooks

## Environment Configuration
```bash
# Web Server
MONGODB_URL=mongodb://mongodb:27017/transcription_db
TRANSCRIPTION_SERVICE_URL=http://transcription:8001
JWT_SECRET_KEY=your_jwt_secret
OPENAI_API_KEY=your_openai_key

# Transcription Service  
WEB_SERVER_URL=http://web:8000
OPENAI_API_KEY=your_openai_key
MAX_CONCURRENT_JOBS=3
STORAGE_DIR=/app/audio_storage

# Client
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
```

## File Structure
```
project/
├── client/              # React frontend application
│   ├── src/components/  # Meeting management components
│   ├── src/hooks/       # WebSocket and API hooks
│   └── src/services/    # API service layers
├── web/                 # FastAPI web server
│   ├── main.py         # FastAPI application with all endpoints
│   ├── database.py     # MongoDB connection and models
│   ├── auth.py         # Authentication middleware
│   └── websocket.py    # WebSocket management
├── transcription/       # Transcription service
│   ├── transcription_service.py  # Main service with internal queue
│   └── audio_processor.py        # Audio processing utilities
├── docker-compose.yml   # All 4 services configuration
└── README.md           # This architecture documentation
```

## Current Implementation Status
- ✅ Basic Web Server and Transcription Service architecture defined
- ✅ Webhook communication pattern established
- ✅ Service boundary rules defined (database access control)
- ⏳ MongoDB integration needed in Web Server
- ⏳ Meeting management APIs to implement
- ⏳ Client application to develop
- ⏳ WebSocket real-time updates to implement
- ⏳ Authentication system to build
- ⏳ Keyword management functionality to create

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

## Development Priorities
1. **Implement MongoDB integration in Web Server** (meeting CRUD, user management)
2. **Create meeting management APIs** (create, list, update, delete)
3. **Build audio upload and chunk handling** (file processing, status tracking)
4. **Develop client application** (meeting UI, real-time updates)
5. **Implement keyword management** (CRUD operations for meeting keywords)
6. **Add authentication system** (user management, JWT tokens)
7. **Optimize real-time updates** (WebSocket efficiency, connection management)