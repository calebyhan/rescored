/**
 * Tests for PlaybackControls component.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PlaybackControls from '../../components/PlaybackControls';

describe('PlaybackControls Component', () => {
  const mockOnPlay = vi.fn();
  const mockOnPause = vi.fn();
  const mockOnStop = vi.fn();
  const mockOnTempoChange = vi.fn();
  const mockOnSeek = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render play, pause, and stop buttons', () => {
    render(<PlaybackControls />);

    expect(screen.getByLabelText(/play/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/pause/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/stop/i)).toBeInTheDocument();
  });

  it('should call onPlay when play button clicked', async () => {
    const user = userEvent.setup();
    render(<PlaybackControls onPlay={mockOnPlay} />);

    const playButton = screen.getByLabelText(/play/i);
    await user.click(playButton);

    expect(mockOnPlay).toHaveBeenCalledTimes(1);
  });

  it('should call onPause when pause button clicked', async () => {
    const user = userEvent.setup();
    render(<PlaybackControls onPause={mockOnPause} isPlaying />);

    const pauseButton = screen.getByLabelText(/pause/i);
    await user.click(pauseButton);

    expect(mockOnPause).toHaveBeenCalledTimes(1);
  });

  it('should call onStop when stop button clicked', async () => {
    const user = userEvent.setup();
    render(<PlaybackControls onStop={mockOnStop} />);

    const stopButton = screen.getByLabelText(/stop/i);
    await user.click(stopButton);

    expect(mockOnStop).toHaveBeenCalledTimes(1);
  });

  it('should disable play button when already playing', () => {
    render(<PlaybackControls isPlaying />);

    const playButton = screen.getByLabelText(/play/i);
    expect(playButton).toBeDisabled();
  });

  it('should show pause button only when playing', () => {
    const { rerender } = render(<PlaybackControls isPlaying={false} />);

    const pauseButton = screen.getByLabelText(/pause/i);
    expect(pauseButton).toBeDisabled();

    rerender(<PlaybackControls isPlaying />);
    expect(pauseButton).not.toBeDisabled();
  });

  it('should render tempo control', () => {
    render(<PlaybackControls tempo={120} />);

    expect(screen.getByLabelText(/tempo/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue('120')).toBeInTheDocument();
  });

  it('should update tempo when slider moved', async () => {
    render(<PlaybackControls tempo={120} onTempoChange={mockOnTempoChange} />);

    const tempoSlider = screen.getByLabelText(/tempo/i);
    fireEvent.change(tempoSlider, { target: { value: '140' } });

    expect(mockOnTempoChange).toHaveBeenCalledWith(140);
  });

  it('should enforce tempo min and max bounds', () => {
    render(<PlaybackControls tempo={120} minTempo={40} maxTempo={240} />);

    const tempoSlider = screen.getByLabelText(/tempo/i) as HTMLInputElement;

    expect(tempoSlider.min).toBe('40');
    expect(tempoSlider.max).toBe('240');
  });

  it('should display current playback position', () => {
    render(<PlaybackControls currentTime={30} duration={180} />);

    // Should show time in format like 0:30 / 3:00
    expect(screen.getByText(/0:30/)).toBeInTheDocument();
    expect(screen.getByText(/3:00/)).toBeInTheDocument();
  });

  it('should render seek bar', () => {
    render(<PlaybackControls currentTime={30} duration={180} />);

    const seekBar = screen.getByRole('slider', { name: /seek/i });
    expect(seekBar).toBeInTheDocument();
  });

  it('should seek when seek bar moved', async () => {
    render(
      <PlaybackControls
        currentTime={30}
        duration={180}
        onSeek={mockOnSeek}
      />
    );

    const seekBar = screen.getByRole('slider', { name: /seek/i });
    fireEvent.change(seekBar, { target: { value: '90' } });

    expect(mockOnSeek).toHaveBeenCalledWith(90);
  });

  it('should show loading state when initializing', () => {
    render(<PlaybackControls loading />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/play/i)).toBeDisabled();
  });

  it('should disable controls when no audio loaded', () => {
    render(<PlaybackControls audioLoaded={false} />);

    expect(screen.getByLabelText(/play/i)).toBeDisabled();
    expect(screen.getByLabelText(/pause/i)).toBeDisabled();
    expect(screen.getByLabelText(/stop/i)).toBeDisabled();
  });

  it('should show volume control', () => {
    render(<PlaybackControls showVolumeControl />);

    expect(screen.getByLabelText(/volume/i)).toBeInTheDocument();
  });

  it('should update volume when volume slider moved', async () => {
    const mockOnVolumeChange = vi.fn();
    render(
      <PlaybackControls
        showVolumeControl
        volume={0.8}
        onVolumeChange={mockOnVolumeChange}
      />
    );

    const volumeSlider = screen.getByLabelText(/volume/i);
    fireEvent.change(volumeSlider, { target: { value: '0.5' } });

    expect(mockOnVolumeChange).toHaveBeenCalledWith(0.5);
  });

  it('should toggle loop mode', async () => {
    const user = userEvent.setup();
    const mockOnLoopToggle = vi.fn();
    render(<PlaybackControls onLoopToggle={mockOnLoopToggle} />);

    const loopButton = screen.getByLabelText(/loop/i);
    await user.click(loopButton);

    expect(mockOnLoopToggle).toHaveBeenCalledWith(true);
  });

  it('should show loop indicator when loop enabled', () => {
    render(<PlaybackControls loop />);

    const loopButton = screen.getByLabelText(/loop/i);
    expect(loopButton).toHaveClass(/active|enabled/);
  });

  it('should format time correctly', () => {
    render(<PlaybackControls currentTime={125} duration={3665} />);

    // 125 seconds = 2:05, 3665 seconds = 1:01:05
    expect(screen.getByText(/2:05/)).toBeInTheDocument();
    expect(screen.getByText(/1:01:05/)).toBeInTheDocument();
  });

  it('should support keyboard shortcuts', async () => {
    const user = userEvent.setup();
    render(
      <PlaybackControls
        onPlay={mockOnPlay}
        onPause={mockOnPause}
        supportKeyboardShortcuts
      />
    );

    // Spacebar should toggle play/pause
    await user.keyboard(' ');
    expect(mockOnPlay).toHaveBeenCalled();
  });
});
