# Development Journey: Architecture & Lessons Learned

## My Approach

When I started this project, I had one main goal: **keep it simple**. I wanted to build something that would meet all the requirements without overcomplicating things, especially given the time constraints. So right from the beginning, I settled on a clean four-container architecture:

- **The web client** - Handles all UX/UI interactions
- **The web server** - The core business logic and database interactions  
- **The database** - Data persistence layer
- **The transcription service** - Interface with OpenAI's API

## Key Architecture Decisions and Trade-offs

### Queue Service Consideration
I considered having a separate container just for queue operations. However, for this demo, I chose simplicity over complexity. For a production-ready service, I would absolutely implement a separate queue service since it's much more robust and easier to debug when issues arise.

### Frontend Silence Detection
I initially planned to implement silence detection on the frontend to send only meaningful audio content to the server. This approach would have reduced both the file transfer overhead between client and web server, and transcription costs by eliminating silent segments upfront. However, I encountered audio file formatting complications that ultimately led me to abandon this optimization step. (See audio formatting issues below)

### Audio File Service Strategy
I also explored the idea of a dedicated audio file handling service. Audio file formatting ended up consuming significantly more development time than I anticipated and essentially became its own complex subsystem. I'll dive into the details of this challenge shortly.

### Shared Volume Implementation
Another decision I made with was implementing a shared volume for audio files, so that both the web server and transcription service can access. This eliminates the need to transfer files between services. In a production environment, I'd likely use S3 storage following the same architectural pattern.

### Database Choice: MongoDB
I selected MongoDB because it naturally handles the meeting data structure, particularly the lists of keywords associated with each meeting. I considered storing meeting files and transcriptions as well, but ran out of development time to implement this fully.

### Transcription Service Philosophy
My approach for the transcription service wa, again, to keep it focused and simple. I intentionally minimized business logic and avoided giving it database access. By centralizing all business logic and database operations in the web server, debugging becomes much more manageable given the current system size.

### Client-Side Keyword Matching
I implemented keyword matching on the client side using straightforward string matching rather than server-side processing. This approach means that when meeting keywords change, the system doesn't need to fetch new transcriptions from the server. 

For more sophisticated matching algorithms that require context analysis, I would definitely move this logic server-side.

---

## The Audio File Formatting Challenge

This is where things got interesting. I spent a substantial portion of development time wrestling with audio formatting issues that proved more complex than initially anticipated.

### The Core Problem
When I created a media stream on the client (in the `AudioRecorder` component) and sent audio chunks to the web server, only the **first chunk** was a properly formatted WebM audio file. All subsequent chunks contained raw WebM data bytes but lacked the necessary headers and metadata; and were considered to be corrupted and unusable.

### Attempted Solutions
I invested considerable time trying to resolve this from the frontend:

- Attempted to make each audio chunk an independent, properly formatted WebM file
- Experimented with different chunk durations 
- Tried various WebM header configurations
- Researched OpenAI Whisper's documentation thoroughly (discovered it requires properly formatted files, not raw streams)
- Explored alternative audio formats (which presented their own implementation challenges)
- **Actually analyzed WebM byte codes** to identify missing headers and metadata

> If anyone has encountered this issue and found a more elegant solution, I genuinely would like to hear about it.

### The Solution: Change of Strategy
After extensive troubleshooting, I decided to completely restructure my approach:

1. **Aggregate** all WebM files for a meeting on the web server
2. **Process** the properly formatted WebM file into chunks
3. **Send** those processed chunks to the transcription service

While not my original vision, this approach proved effective and reliable.

## Areas for Future Improvement

### Dedicated Audio Processing Service
Given more time, I would implement a separate service specifically for audio and file operations, likely designed as a queue or event-based system. This would better handle concurrency scenarios when multiple clients connect to the same meeting.

### Persistent Processing State
Currently, the processed timer for each meeting is stored in memory, which isn't ideal. I would move this to database storage for better reliability.

**Known Issue**: When a new WebSocket connection is established for an existing meeting, transcription starts from the beginning of the raw audio file rather than resuming from the last processing point. A temporary workaround is deleting meeting-related audio files after each recording session ends.

---

## Reflection

Looking back, I'm satisfied that I managed to maintain system simplicity throughout the implementation process. I would probably spend less time trying to solve the front-end audio formatting issue and pivot to the server-side aggregation approach sooner. But you don't know how deep the rabbit hole is until you dive into these technical challenges. I'm glad that I investigated the problem domain, recognized it was becoming a significant time investment, and strategically shifted to a more viable approach before too late.