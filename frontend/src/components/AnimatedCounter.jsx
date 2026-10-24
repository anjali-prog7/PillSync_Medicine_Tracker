import { useState, useEffect, useRef } from "react";

function AnimatedCounter({ value = 0, duration = 1500, suffix = "", prefix = "", decimals = 0 }) {
  const [displayValue, setDisplayValue] = useState(0);
  const counterRef = useRef(null);
  const hasAnimated = useRef(false);
  const animationFrame = useRef(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated.current) {
          hasAnimated.current = true;
          const startTime = performance.now();
          const startValue = 0;
          const endValue = value;

          const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = startValue + (endValue - startValue) * eased;
            setDisplayValue(current);
            if (progress < 1) {
              animationFrame.current = requestAnimationFrame(animate);
            } else {
              setDisplayValue(endValue);
            }
          };
          animationFrame.current = requestAnimationFrame(animate);
        }
      },
      { threshold: 0.1 }
    );

    if (counterRef.current) {
      observer.observe(counterRef.current);
    }

    return () => {
      if (animationFrame.current) {
        cancelAnimationFrame(animationFrame.current);
      }
      observer.disconnect();
    };
  }, [value, duration]);

  useEffect(() => {
    hasAnimated.current = false;
  }, [value]);

  const formattedValue = Number(displayValue).toFixed(decimals);

  return (
    <span ref={counterRef} className="animated-counter">
      {prefix}{formattedValue}{suffix}
    </span>
  );
}

export default AnimatedCounter;
