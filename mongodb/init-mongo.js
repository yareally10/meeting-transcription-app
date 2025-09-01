db = db.getSiblingDB('meeting_db');

db.createCollection('meetings');
db.createCollection('users');

db.meetings.createIndex({ "created_by": 1 });
db.meetings.createIndex({ "created_at": -1 });
db.meetings.createIndex({ "status": 1 });
db.meetings.createIndex({ "keywords": 1 });

db.users.createIndex({ "email": 1 }, { unique: true });

print('Database initialized successfully');