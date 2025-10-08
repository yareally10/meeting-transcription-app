db = db.getSiblingDB('meeting_db');

db.createCollection('meetings');

db.meetings.createIndex({ "created_at": -1 });
db.meetings.createIndex({ "status": 1 });
db.meetings.createIndex({ "keywords": 1 });

print('Database initialized successfully');