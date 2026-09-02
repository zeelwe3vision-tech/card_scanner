"use client";

import React, { useState } from "react";
import { Camera, FileText, Link } from "lucide-react";
import { cn } from "@/lib/utils";
import ScanUploader from "./ScanUploader";
import PdfUploader from "./PdfUploader";


type TabType = "scan" | "pdf";

const tabs = [
  { id: "scan" as TabType, label: "Scan", icon: Camera },
  { id: "pdf" as TabType, label: "PDF", icon: FileText },
];

export default function UploadTabs() {
  const [activeTab, setActiveTab] = useState<TabType>("scan");

  return (
    <div className="w-full max-w-2xl mx-auto">
      {/* Tabs */}
      <div className="flex border-b border-gray-200 mb-6">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium transition-colors",
                isActive
                  ? "border-b-2 border-primary-600 text-primary-600"
                  : "text-gray-500 hover:text-gray-700"
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="mt-4">
        {activeTab === "scan" && <ScanUploader />}
        {activeTab === "pdf" && <PdfUploader />}
      </div>
    </div>
  );
}