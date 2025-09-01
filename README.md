# Meeting Transcription Platform

A comprehensive meeting transcription platform with microservices architecture.

## Architecture

- **Client**: React frontend with Vite (Port 3000)
- **Web Server**: FastAPI backend with MongoDB integration (Port 8000)
- **MongoDB**: Database for persistent storage (Port 27017)

## Quick Start

1. Clone the repository
2. Copy environment variables:
   ```bash
   cp .env.example .env
   ```
3. Start all services:
   ```bash
   docker-compose up --build
   ```
4. Access the application:
   - Frontend: http://localhost:3000
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## Features

- Meeting CRUD operations
- Keywords management
- Real-time updates (planned)
- Audio transcription (planned)

## API Endpoints

- `POST /meetings` - Create new meeting
- `GET /meetings` - List all meetings
- `GET /meetings/{id}` - Get meeting details
- `PUT /meetings/{id}` - Update meeting
- `DELETE /meetings/{id}` - Delete meeting
- `PUT /meetings/{id}/keywords` - Update meeting keywords

## Development

Each service can be developed independently:

### Client
```bash
cd client
npm install
npm run dev
```

### Web Server
```bash
cd web-server
pip install -r requirements.txt
uvicorn main:app --reload
```