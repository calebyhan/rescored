import { useEffect, useRef } from 'react';
import { Renderer, Stave, StaveNote, Voice, Formatter } from 'vexflow';

interface DurationButtonProps {
  duration: string;
  isActive: boolean;
  onClick: () => void;
  title: string;
}

export function DurationButton({ duration, isActive, onClick, title }: DurationButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    containerRef.current.innerHTML = '';

    try {
      const W = 60;
      const H = 60;

      const renderer = new Renderer(containerRef.current, Renderer.Backends.SVG);
      renderer.resize(W, H);
      const context = renderer.getContext();

      // Make a stave ONLY for positioning (do NOT draw it)
      // Y controls vertical placement of the note on the staff “grid”.
      const stave = new Stave(-12, -20, W + 24);
      stave.setContext(context);
      // IMPORTANT: no stave.draw();

      const durationMap: Record<string, string> = {
        whole: 'w',
        half: 'h',
        quarter: 'q',
        eighth: '8',
        '16th': '16',
        '32nd': '32',
      };
      const vfDuration = durationMap[duration] || 'q';

      const note = new StaveNote({
        keys: ['b/4'],
        duration: vfDuration,
        clef: 'treble',
      });

      const voice = new Voice({ num_beats: 4, beat_value: 4 });
      voice.setStrict(false);
      voice.addTickables([note]);

      // Give VF some room to lay out flags/stems
      new Formatter().joinVoices([voice]).format([voice], W);

      // --- Center the note horizontally ---
      // After formatting, VexFlow has assigned X positions.
      // Shift so the note's X is centered in the SVG.
      note.setStave(stave);

      // Draw just the note (no visible staff)
      voice.draw(context, stave);

      // --- VISUAL CENTERING FIX ---
      const svg = containerRef.current.querySelector('svg');
      if (svg) {
        const group = svg.querySelector('g');
        if (group) {
          const bbox = group.getBBox();
          const dx = W / 2 - (bbox.x + bbox.width / 2);
          group.setAttribute(
            'transform',
            `translate(${dx}, 0)`
          );
        }

        svg.style.overflow = 'visible';

        const els = svg.querySelectorAll('path, line, rect, circle, ellipse');
        els.forEach((el) => {
          const e = el as SVGElement;
          if (isActive) {
            e.setAttribute('fill', 'white');
            e.setAttribute('stroke', 'white');
          } else {
            e.removeAttribute('fill');
            e.removeAttribute('stroke');
          }
        });
      }

    } catch (err) {
      console.error(err);
      if (containerRef.current) containerRef.current.textContent = duration[0]?.toUpperCase() ?? '?';
    }
  }, [duration, isActive]);


  return (
    <button
      className={`duration-button-inline ${isActive ? 'active' : ''}`}
      onClick={onClick}
      title={title}
      type="button"
    >
      <div ref={containerRef} className="duration-button-vexflow" />
    </button>
  );
}
