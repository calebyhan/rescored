/**
 * Test fixtures and sample data.
 */

export const sampleMusicXML = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1">
      <part-name>Piano</part-name>
    </score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key>
          <fifths>0</fifths>
        </key>
        <time>
          <beats>4</beats>
          <beat-type>4</beat-type>
        </time>
        <clef>
          <sign>G</sign>
          <line>2</line>
        </clef>
      </attributes>
      <note>
        <pitch>
          <step>C</step>
          <octave>4</octave>
        </pitch>
        <duration>4</duration>
        <type>whole</type>
      </note>
    </measure>
  </part>
</score-partwise>`;

export const sampleJobResponse = {
  job_id: 'test-job-123',
  status: 'queued',
  created_at: '2025-01-01T00:00:00Z',
  estimated_duration_seconds: 120,
  websocket_url: 'ws://localhost:8000/api/v1/jobs/test-job-123/stream',
};

export const sampleJobStatus = {
  job_id: 'test-job-123',
  status: 'processing',
  progress: 50,
  current_stage: 'transcription',
  status_message: 'Transcribing audio to MIDI',
  created_at: '2025-01-01T00:00:00Z',
  started_at: '2025-01-01T00:00:05Z',
  completed_at: null,
  failed_at: null,
  error: null,
  result_url: null,
};

export const sampleCompletedJob = {
  ...sampleJobStatus,
  status: 'completed',
  progress: 100,
  current_stage: 'completed',
  status_message: 'Transcription complete',
  completed_at: '2025-01-01T00:02:00Z',
  result_url: '/api/v1/scores/test-job-123',
};

export const sampleFailedJob = {
  ...sampleJobStatus,
  status: 'failed',
  progress: 25,
  current_stage: 'audio_download',
  status_message: 'Download failed',
  failed_at: '2025-01-01T00:00:30Z',
  error: {
    message: 'Video unavailable',
    stage: 'audio_download',
  },
};

export const sampleProgressUpdate = {
  type: 'progress',
  job_id: 'test-job-123',
  progress: 75,
  stage: 'musicxml',
  message: 'Generating MusicXML',
  timestamp: '2025-01-01T00:01:30Z',
};

export const sampleCompletedUpdate = {
  type: 'completed',
  job_id: 'test-job-123',
  progress: 100,
  stage: 'completed',
  message: 'Transcription complete',
  timestamp: '2025-01-01T00:02:00Z',
  result_url: '/api/v1/scores/test-job-123',
};

export const sampleErrorUpdate = {
  type: 'error',
  job_id: 'test-job-123',
  progress: 25,
  stage: 'audio_download',
  message: 'Download failed',
  timestamp: '2025-01-01T00:00:30Z',
  error: {
    message: 'Video unavailable',
    stage: 'audio_download',
  },
};

export const sampleParsedScore = {
  measures: [
    {
      number: 1,
      notes: [
        {
          pitch: 'C4',
          duration: 'w',
          type: 'note',
        },
      ],
      attributes: {
        timeSignature: { beats: 4, beatType: 4 },
        keySignature: { fifths: 0 },
        clef: { sign: 'G', line: 2 },
      },
    },
  ],
  metadata: {
    title: 'Test Score',
    tempo: 120,
  },
};
