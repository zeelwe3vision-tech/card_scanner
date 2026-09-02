"use client";

import React from "react";
import Link from "next/link";
import { CreditCard, Plus } from "lucide-react";
import Button from "@/components/ui/Button";

export default function EmptyState() {
  return (
    <div className="text-center py-16 px-4">
      <div className="mx-auto w-20 h-20 bg-primary-50 rounded-full flex items-center justify-center mb-6">
        <CreditCard className="h-10 w-10 text-primary-600" />
      </div>

      <h3 className="text-xl font-semibold text-gray-900 mb-2">
        No business cards yet
      </h3>

      <p className="text-gray-500 mb-8 max-w-md mx-auto">
        Upload your first business card by scanning, uploading a PDF, or pasting a URL.
      </p>

      <Link href="/">
        <Button>
          <Plus className="h-4 w-4 mr-2" />
          Add Business Card
        </Button>
      </Link>
    </div>
  );
}