# Meeting Transcription Platform

A meeting transcription platform with microservices architecture that provides real-time audio processing, meeting management, and AI-powered transcription capabilities.

## Architecture

The platform consists of five main services:

- **Client**: React frontend with Vite and TypeScript (Port 3000)
- **Web Server**: FastAPI backend with MongoDB integration and WebSocket support (Port 8000)
- **Transcription Service**: Dedicated OpenAI Whisper transcription service with Redis queue (Port 8001)
- **MongoDB**: Database for persistent storage (Port 27017)
- **Redis**: Job queue and session management (Port 6379)

### Service Communication
- Web Server ↔ MongoDB: Database operations
- Web Server ↔ Transcription Service: HTTP API calls and webhooks
- Transcription Service ↔ Redis: Job queue management with persistence
- Client ↔ Web Server: REST API and WebSocket connections
- Shared audio storage between Web Server and Transcription Service

## Setup Instructions

### Prerequisites
- Docker and Docker Compose
- OpenAI API key for transcription service

### Quick Start
1. Clone the repository:
   ```bash
   git clone https://github.com/yareally10/meeting-transcription-app.git
   cd meeting-transcription-app
   ```

2. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

3. Start all services:
   ```bash
   docker-compose up --build
   ```

4. Access the services:
   - **Frontend**: http://localhost:3000
   - **Web Server API**: http://localhost:8000
   - **API Documentation**: http://localhost:8000/docs
   - **Transcription Service**: http://localhost:8001
   - **Redis**: localhost:6379 (internal service)

## Key Features

### Meeting Management
- Create, read, update, and delete meetings
- Keywords management
- Meeting status tracking

### Audio Processing & Transcription
- Real-time audio upload and processing
- OpenAI Whisper-powered transcription
- Redis-backed job queue with persistence
- Asynchronous job processing with multi-worker support
- Webhook-based result notifications
- Support for multiple concurrent transcription jobs (configurable, default: 3)

### Real-time Features
- WebSocket connections for live updates
- Real-time transcription status updates
- Live meeting state synchronization

### API & Integration
- RESTful API design
- OpenAPI/Swagger documentation
- Webhook system for service integration
- Health monitoring and statistics endpoints

## API Documentation

### Web Server API (Port 8000)
- **Swagger UI**: http://localhost:8000/docs
- **OpenAPI Spec**: http://localhost:8000/openapi.json

#### Meeting Endpoints
- `POST /meetings` - Create new meeting
- `GET /meetings` - List all meetings with pagination
- `GET /meetings/{id}` - Get meeting details
- `PUT /meetings/{id}` - Update meeting
- `DELETE /meetings/{id}` - Delete meeting
- `PUT /meetings/{id}/keywords` - Update meeting keywords

#### Transcription Endpoints
- `GET /transcription/health` - Check transcription service health
- `GET /transcription/job/{job_id}` - Get transcription job status
- `POST /webhook/transcription-completed` - Webhook for transcription results

### Transcription Service API (Port 8001)
- **Health Check**: http://localhost:8001/health
- **Statistics**: http://localhost:8001/stats

#### Transcription Endpoints
- `POST /transcribe` - Submit audio file for transcription
- `GET /job/{job_id}` - Get job status
- `GET /stats` - Get processing statistics
- `GET /health` - Service health and queue status

## Development Setup

Each service can be developed independently:

### Client (React + TypeScript)
```bash
cd client
npm install
npm run dev
```

### Web Server (FastAPI)
```bash
cd web-server
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Transcription Service (FastAPI + OpenAI)
```bash
cd transcription
pip install -r requirements.txt
export OPENAI_API_KEY=your-api-key
uvicorn main:app --reload --port 8001
```

### Environment Variables

Required environment variables:
- `OPENAI_API_KEY`: Your OpenAI API key for transcription
- `MONGODB_URL`: MongoDB connection string (default: mongodb://mongodb:27017)
- `REDIS_URL`: Redis connection string (default: redis://redis:6379)
- `MAX_CONCURRENT_JOBS`: Number of concurrent transcription workers (default: 3)

### Service Architecture Details

#### Transcription Service
- **Modular Design**: Clean separation of concerns with dedicated modules
  - `config.py`: Configuration management
  - `job_manager.py`: Job lifecycle and Redis queue management
  - `redis_queue.py`: Redis queue operations
  - `webhook_handler.py`: Webhook notifications
  - `transcription_worker.py`: Worker thread management
- **Worker Threads**: Configurable number of concurrent transcription workers
- **Queue System**: Redis-backed job queue with persistence and 24-hour TTL for job status
- **Error Handling**: Comprehensive error handling and logging

#### Web Server
- **WebSocket Support**: Real-time communication with clients
- **MongoDB Integration**: Persistent storage with async operations
- **Service Integration**: HTTP client for transcription service
- **Webhook Handling**: Receives transcription completion notifications

## Monitoring & Health Checks

- **Web Server Health**: http://localhost:8000/
- **Transcription Service Health**: http://localhost:8001/health
- **Transcription Statistics**: http://localhost:8001/stats
- **MongoDB**: Standard MongoDB monitoring on port 27017
- **Redis**: Redis CLI monitoring on port 6379

All services include Docker health checks with automatic restart policies.

## File Structure
```
meeting-transcription-app/
├── client/                # React frontend
├── web-server/            # FastAPI web server
├── transcription/         # Transcription service with Redis queue
├── mongodb/               # Database initialization scripts
├── volumes/               # Persistent data storage
│   ├── mongodb/           # MongoDB data
│   ├── redis/             # Redis data with AOF persistence
│   └── shared_audio/      # Audio files organized by meeting ID
│       └── {meeting_id}/
│           └── audio/     # Audio chunks by session
└── docker-compose.yml     # Service orchestration with health checks
```

## License

MIT License - Copyright (c) 2025 yareally10

See [LICENSE](LICENSE) file for details.