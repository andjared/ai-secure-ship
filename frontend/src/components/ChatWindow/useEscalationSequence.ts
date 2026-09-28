import { useEffect, useRef, useState } from "react";
import { HandoffLineKind } from "../../api/generated/chat";
import type { HandoffLine } from "../../api/generated/chat";

const LINE_DELAY_MS = 1500;

/**
 * Plays the scripted human handoff one line at a time. The first line shows
 * at once and shifts the window to the escalated look; the rest follow on a
 * timer while isPlaying is true. Lines after the "has entered the chat"
 * system line, or in an already escalated chat, are from the human.
 */
export function useEscalationSequence(
  appendLine: (line: HandoffLine, isFromHuman: boolean) => void,
) {
  const [isEscalated, setIsEscalated] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    // Timer ids are only ever pushed onto this array, never replaced.
    const pendingTimers = timers.current;
    return () => pendingTimers.forEach((timer) => clearTimeout(timer));
  }, []);

  function start(handoff: HandoffLine[]) {
    let hasHumanJoined = isEscalated;
    const lines = handoff.map((line) => {
      const isFromHuman = hasHumanJoined;
      if (line.kind === HandoffLineKind.system) hasHumanJoined = true;
      return { line, isFromHuman };
    });

    const [first, ...rest] = lines;
    if (!first) return;

    appendLine(first.line, first.isFromHuman);
    setIsEscalated(true);
    if (rest.length === 0) return;

    setIsPlaying(true);
    rest.forEach(({ line, isFromHuman }, index) => {
      const timer = window.setTimeout(() => {
        appendLine(line, isFromHuman);
        if (index === rest.length - 1) setIsPlaying(false);
      }, LINE_DELAY_MS * (index + 1));
      timers.current.push(timer);
    });
  }

  return { start, isEscalated, isPlaying };
}
