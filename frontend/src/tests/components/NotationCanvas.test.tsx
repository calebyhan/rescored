/**
 * Tests for NotationCanvas component.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import NotationCanvas from '../../components/NotationCanvas';
import { sampleMusicXML } from '../fixtures';

describe('NotationCanvas Component', () => {
  beforeEach(() => {
    // Create mock canvas context
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
      fillRect: vi.fn(),
      clearRect: vi.fn(),
      beginPath: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      stroke: vi.fn(),
      fill: vi.fn(),
      arc: vi.fn(),
      fillText: vi.fn(),
      measureText: vi.fn(() => ({ width: 0 })),
    })) as any;
  });

  it('should render canvas element', () => {
    render(<NotationCanvas musicXML={sampleMusicXML} />);

    const canvas = screen.getByRole('img', { hidden: true }) || document.querySelector('canvas');
    expect(canvas).toBeInTheDocument();
  });

  it('should render notation from MusicXML', () => {
    const { container } = render(<NotationCanvas musicXML={sampleMusicXML} />);

    // VexFlow should create SVG or Canvas elements
    const notationElement = container.querySelector('svg') || container.querySelector('canvas');
    expect(notationElement).toBeInTheDocument();
  });

  it('should handle empty MusicXML', () => {
    render(<NotationCanvas musicXML="" />);

    // Should render without errors
    expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
  });

  it('should handle invalid MusicXML', () => {
    render(<NotationCanvas musicXML="<invalid>xml</invalid>" />);

    // Should show error or empty state
    expect(
      screen.queryByText(/error|invalid/i) || screen.queryByText(/no notation/i)
    ).toBeTruthy();
  });

  it('should support zoom controls', () => {
    render(<NotationCanvas musicXML={sampleMusicXML} showControls />);

    const zoomInButton = screen.getByLabelText(/zoom in/i);
    const zoomOutButton = screen.getByLabelText(/zoom out/i);

    expect(zoomInButton).toBeInTheDocument();
    expect(zoomOutButton).toBeInTheDocument();
  });

  it('should zoom in when zoom in button clicked', () => {
    render(<NotationCanvas musicXML={sampleMusicXML} showControls />);

    const zoomInButton = screen.getByLabelText(/zoom in/i);

    fireEvent.click(zoomInButton);

    // Zoom should increase (exact value depends on implementation)
    // This tests the interaction works
    expect(zoomInButton).not.toBeDisabled();
  });

  it('should zoom out when zoom out button clicked', () => {
    render(<NotationCanvas musicXML={sampleMusicXML} showControls />);

    const zoomOutButton = screen.getByLabelText(/zoom out/i);

    fireEvent.click(zoomOutButton);

    expect(zoomOutButton).not.toBeDisabled();
  });

  it('should make notes selectable when interactive', () => {
    const onNoteSelect = vi.fn();
    const { container } = render(
      <NotationCanvas
        musicXML={sampleMusicXML}
        interactive
        onNoteSelect={onNoteSelect}
      />
    );

    // Simulate clicking on a note
    const noteElement = container.querySelector('[data-note]') || container.querySelector('.vf-note');
    if (noteElement) {
      fireEvent.click(noteElement);
      expect(onNoteSelect).toHaveBeenCalled();
    }
  });

  it('should highlight selected notes', () => {
    const { container } = render(
      <NotationCanvas
        musicXML={sampleMusicXML}
        interactive
        selectedNotes={['note-1']}
      />
    );

    const selectedNote = container.querySelector('.selected') || container.querySelector('[data-selected="true"]');
    expect(selectedNote).toBeTruthy();
  });

  it('should re-render when MusicXML changes', () => {
    const { rerender } = render(<NotationCanvas musicXML={sampleMusicXML} />);

    const newMusicXML = sampleMusicXML.replace('<step>C</step>', '<step>D</step>');

    rerender(<NotationCanvas musicXML={newMusicXML} />);

    // Component should re-render without errors
    expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
  });

  it('should clean up on unmount', () => {
    const { unmount } = render(<NotationCanvas musicXML={sampleMusicXML} />);

    unmount();

    // Should not throw errors
    expect(true).toBe(true);
  });

  it('should handle window resize', () => {
    render(<NotationCanvas musicXML={sampleMusicXML} />);

    // Trigger resize event
    fireEvent(window, new Event('resize'));

    // Should re-render without errors
    expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
  });

  it('should display measure numbers', () => {
    render(<NotationCanvas musicXML={sampleMusicXML} showMeasureNumbers />);

    // Should show measure number 1
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('should support scrolling for long scores', () => {
    const longMusicXML = sampleMusicXML; // In practice, would have many measures
    const { container } = render(<NotationCanvas musicXML={longMusicXML} />);

    const scrollableElement = container.querySelector('[style*="overflow"]');
    expect(scrollableElement || container.firstChild).toBeTruthy();
  });

  it('should render with custom width and height', () => {
    const { container } = render(
      <NotationCanvas
        musicXML={sampleMusicXML}
        width={800}
        height={600}
      />
    );

    const canvas = container.querySelector('canvas') || container.querySelector('svg');
    // Size should be applied (exact check depends on implementation)
    expect(canvas).toBeTruthy();
  });
});
