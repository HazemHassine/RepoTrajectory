"use client";

import React from "react";

export function MotionShell({ children }: { children: React.ReactNode }) {
  return <div className="min-h-[calc(100vh-120px)]">{children}</div>;
}
