"use client";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface PanelSectionProps {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}

export function PanelSection({ title, icon, children }: PanelSectionProps) {
  const [show, setShow] = useState(true);

  return (
    <div className="mb-5">
      <h2
        className="text-lg font-semibold mb-3 text-[#0B1517] flex items-center justify-between cursor-pointer"
        onClick={() => setShow(!show)}
      >
        <div className="flex items-center">
          <span className="bg-[#52B2CD]/15 text-[#16749D] p-1.5 rounded-lg mr-2 shadow-sm border border-[#16749D]/40">
            {icon}
          </span>
          <span>{title}</span>
        </div>
        {show ? (
          <ChevronDown className="h-4 w-4 text-[#0B1517]" />
        ) : (
          <ChevronRight className="h-4 w-4 text-[#0B1517]" />
        )}
      </h2>
      {show && children}
    </div>
  );
}
