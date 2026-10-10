import { animate } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { prefersReducedMotion } from "../../animations/motion";

export function CountUp({ value, duration = 0.9, format = (n: number) => String(Math.round(n)) }: {
  value: number; duration?: number; format?: (n: number) => string;
}) {
  const [display, setDisplay] = useState(() => (prefersReducedMotion() ? value : 0));
  const from = useRef(0);

  useEffect(() => {
    if (prefersReducedMotion()) {
      setDisplay(value);
      return;
    }
    const controls = animate(from.current, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setDisplay(v),
    });
    from.current = value;
    return () => controls.stop();
  }, [value, duration]);

  return <>{format(display)}</>;
}
