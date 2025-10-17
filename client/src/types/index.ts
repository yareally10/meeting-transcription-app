export interface Meeting {
  id: string;
  title: string;
  description: string;
  createdAt: string;
  updatedAt: string;
  status: 'created' | 'uploading' | 'transcribing' | 'completed' | 'failed';
  keywords: string[];
  fullTranscription?: string;
  metadata?: {
    language?: string;
    participants?: string[];
    totalDuration?: number;
    processingStarted?: string;
    processingCompleted?: string;
    totalProcessingTime?: number;
  };
}

export interface CreateMeetingRequest {
  title: string;
  description: string;
  keywords: string[];
}

export interface UpdateMeetingRequest {
  title?: string;
  description?: string;
  keywords?: string[];
}