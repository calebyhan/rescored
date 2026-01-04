# Rescored Documentation

## Project Vision

Rescored is an AI-powered music transcription and notation editor that converts YouTube videos into editable sheet music. Musicians can paste a URL, get professional-quality notation, edit it, and export in standard formats.

## What This Documentation Covers

This documentation serves as the technical blueprint for implementing Rescored. It focuses on:

- **Architecture & Design**: System structure, technology choices, and rationale
- **Backend Processing**: Audio extraction, ML transcription pipeline, API design
- **Frontend Interface**: Sheet music rendering, interactive editing, playback
- **Integration**: How components communicate and data flows through the system
- **Implementation Roadmap**: MVP scope and future feature phases

## Reading Guide

### For Full-Stack Developers (Start Here)
1. [Getting Started](getting-started.md) - Overview and context
2. [Architecture Overview](architecture/overview.md) - How everything fits together
3. [MVP Scope](features/mvp.md) - What to build first
4. Deep dive into [Backend](backend/) and [Frontend](frontend/) sections

### For Backend Engineers
1. [Architecture Overview](architecture/overview.md)
2. [Technology Stack](architecture/tech-stack.md) - Backend choices
3. [Audio Processing Pipeline](backend/pipeline.md) - Core workflow
4. [API Design](backend/api.md)
5. [Background Workers](backend/workers.md)
6. [Testing Guide](backend/testing.md) - Writing and running tests

### For Frontend Engineers
1. [Architecture Overview](architecture/overview.md)
2. [Technology Stack](architecture/tech-stack.md) - Frontend choices
3. [Notation Rendering](frontend/notation-rendering.md)
4. [Interactive Editor](frontend/editor.md)
5. [Playback System](frontend/playback.md)
6. [Data Flow](frontend/data-flow.md)

### For Product/Design
1. [MVP Scope](features/mvp.md)
2. [Architecture Overview](architecture/overview.md) - User flow
3. [Known Challenges](research/challenges.md) - Limitations to design around

## Documentation Structure

### Architecture
- [System Overview](architecture/overview.md) - High-level architecture and data flow
- [Technology Stack](architecture/tech-stack.md) - Tech choices with alternatives and trade-offs
- [Deployment Strategy](architecture/deployment.md) - Infrastructure and scaling

### Backend
- [Audio Processing Pipeline](backend/pipeline.md) - End-to-end audio → notation workflow
- [API Design](backend/api.md) - REST endpoints and WebSocket protocol
- [Background Workers](backend/workers.md) - Async job processing with Celery
- [Testing Guide](backend/testing.md) - Backend test suite and best practices

### Frontend
- [Notation Rendering](frontend/notation-rendering.md) - Sheet music display with VexFlow
- [Interactive Editor](frontend/editor.md) - Editing operations and state management
- [Playback System](frontend/playback.md) - Audio synthesis with Tone.js
- [Data Flow](frontend/data-flow.md) - State management and API integration

### Integration
- [File Formats](integration/file-formats.md) - MusicXML, MIDI, internal JSON
- [WebSocket Protocol](integration/websocket-protocol.md) - Real-time progress updates

### Features
- [MVP Scope](features/mvp.md) - Phase 1 features and future roadmap
- [Instrument Remapping](features/instrument-remapping.md) - Cross-instrument conversion (future)

### Research
- [ML Model Selection](research/ml-models.md) - Model comparison and benchmarks
- [Technical Challenges](research/challenges.md) - Known limitations and edge cases

### Reference
- [Getting Started](getting-started.md) - How to use this documentation
- [Glossary](glossary.md) - Musical and technical terminology

## Key Principles

1. **MVP First**: Focus on single-instrument (piano) transcription before multi-instrument
2. **Quality Over Speed**: Prioritize transcription accuracy over processing time
3. **Editable Output**: Transcription won't be perfect—editor is critical for fixing errors
4. **Standard Formats**: Use MusicXML/MIDI for maximum compatibility
5. **Async Everything**: Audio processing is slow—use queues and WebSocket updates

## Quick Reference

**Primary Use Case**: YouTube URL → Transcribed piano sheet music → Edit → Export

**Tech Stack Summary**:
- Frontend: React + VexFlow + Tone.js
- Backend: Python/FastAPI + Celery + Redis
- ML: Demucs (source separation) + basic-pitch (transcription)
- Formats: MusicXML (primary), MIDI (export)

**MVP Timeline**: Focused on getting piano transcription working end-to-end with basic editing

## Contributing to Documentation

As implementation progresses, update these docs with:
- Actual code examples and API samples
- Performance benchmarks and metrics
- Lessons learned and gotchas
- Configuration details and environment setup

## Need Help?

- See [Glossary](glossary.md) for terminology
- Check [Challenges](research/challenges.md) for known issues
- Review [Tech Stack](architecture/tech-stack.md) for decision context
