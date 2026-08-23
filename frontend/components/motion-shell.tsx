"use client";

import { AnimatePresence, motion, MotionConfig, useScroll, useSpring } from "motion/react";
import { usePathname } from "next/navigation";

export function MotionShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 220, damping: 32, mass: .25 });

  return (
    <MotionConfig reducedMotion="user" transition={{ duration: .42, ease: [.22, 1, .36, 1] }}>
      <motion.div className="fixed inset-x-0 top-0 z-[80] h-[2px] origin-left bg-[#c7ff00]" style={{ scaleX }} />
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={pathname}
          className="route-frame page-shell"
          initial={{ opacity: 0, y: 14, clipPath: "inset(0 0 7% 0)" }}
          animate={{ opacity: 1, y: 0, clipPath: "inset(0 0 0% 0)" }}
          exit={{ opacity: 0, y: -8, clipPath: "inset(0 0 4% 0)" }}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </MotionConfig>
  );
}
