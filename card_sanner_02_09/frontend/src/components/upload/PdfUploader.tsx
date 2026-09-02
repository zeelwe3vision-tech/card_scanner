
"use client";

import React, { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { FileText, Upload, X } from "lucide-react";
import Button from "@/components/ui/Button";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import { uploadPdfs } from "@/services/api";

export default function PdfUploader() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFileChange = (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const selectedFiles = Array.from(e.target.files || []);

    if (selectedFiles.length === 0) {
      return;
    }

    const invalidFile = selectedFiles.find(
      (selectedFile) =>
        selectedFile.type !== "application/pdf" &&
        !selectedFile.name.toLowerCase().endsWith(".pdf")
    );

    if (invalidFile) {
      setError("Please select only valid PDF files");
      return;
    }

    setFiles((previousFiles) => [
      ...previousFiles,
      ...selectedFiles.filter(
        (newFile) =>
          !previousFiles.some(
            (existingFile) =>
              existingFile.name === newFile.name &&
              existingFile.size === newFile.size &&
              existingFile.lastModified === newFile.lastModified
          )
      ),
    ]);

    setError(null);

    // Allow selecting the same file again
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files || []);

    if (droppedFiles.length === 0) {
      return;
    }

    const invalidFile = droppedFiles.find(
      (droppedFile) =>
        droppedFile.type !== "application/pdf" &&
        !droppedFile.name.toLowerCase().endsWith(".pdf")
    );

    if (invalidFile) {
      setError("Please drop only valid PDF files");
      return;
    }

    setFiles((previousFiles) => [
      ...previousFiles,
      ...droppedFiles.filter(
        (newFile) =>
          !previousFiles.some(
            (existingFile) =>
              existingFile.name === newFile.name &&
              existingFile.size === newFile.size &&
              existingFile.lastModified === newFile.lastModified
          )
      ),
    ]);

    setError(null);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleRemove = (index: number) => {
    setFiles((previousFiles) =>
      previousFiles.filter(
        (_, fileIndex) => fileIndex !== index
      )
    );

    setError(null);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleRemoveAll = () => {
    setFiles([]);
    setError(null);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      setError("Please select at least one PDF file");
      return;
    }
  
    setIsLoading(true);
    setError(null);
  
    try {
      const response = await uploadPdfs(files);
  
      if (!response.success) {
        setError(
          response.message ||
            "Failed to extract card details from PDFs"
        );
        return;
      }
  
      // ==========================================
      // Multiple Cards
      // ==========================================
  
      if (response.card && response.card.length > 0) {
        // Store all extracted cards
        sessionStorage.setItem(
          "extractedCards",
          JSON.stringify(response.card)
        );
  
        // Keep first card for existing review flow
        sessionStorage.setItem(
          "extractedCard",
          JSON.stringify(response.card[0])
        );
  
        router.push("/review");
        return;
      }
  
      setError(
        response.message ||
          "No business card details were extracted from the PDFs"
      );
    } catch (err: any) {
      setError(
        err?.message ||
          "Something went wrong while processing the PDFs"
      );
    } finally {
      setIsLoading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024)
      return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  return (
    <div className="space-y-6">
      {/* Upload Area */}
      <div
        onClick={() => fileInputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
          isDragging
            ? "border-primary-500 bg-primary-50"
            : "border-gray-300 hover:border-primary-500 hover:bg-primary-50"
        }`}
      >
        <FileText className="mx-auto h-12 w-12 text-gray-400 mb-4" />

        <p className="text-lg font-medium text-gray-700">
          Upload PDFs
        </p>

        <p className="text-sm text-gray-500 mt-1">
          Drag & drop or click to select multiple PDF files
        </p>

        <p className="text-xs text-gray-400 mt-2">
          You can select multiple business card PDFs
        </p>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          multiple
          onChange={handleFileChange}
          className="hidden"
        />
      </div>

      {/* Selected Files */}
      {files.length > 0 && (
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-gray-800">
                Selected PDFs
              </h3>

              <p className="text-xs text-gray-500 mt-1">
                {files.length}{" "}
                {files.length === 1 ? "PDF" : "PDFs"} selected
              </p>
            </div>

            <button
              type="button"
              onClick={handleRemoveAll}
              disabled={isLoading}
              className="text-sm text-red-600 hover:text-red-700 font-medium disabled:opacity-50"
            >
              Remove all
            </button>
          </div>

          {/* File List */}
          <div className="space-y-3">
            {files.map((currentFile, index) => (
              <div
                key={`${currentFile.name}-${currentFile.size}-${currentFile.lastModified}`}
                className="border border-gray-200 rounded-xl p-6 flex items-center justify-between bg-gray-50"
              >
                <div className="flex items-center gap-4 min-w-0">
                  <div className="bg-red-100 p-3 rounded-lg flex-shrink-0">
                    <FileText className="h-8 w-8 text-red-600" />
                  </div>

                  <div className="min-w-0">
                    <p className="text-xs text-gray-400 mb-1">
                      PDF {index + 1}
                    </p>

                    <p className="font-medium text-gray-800 truncate max-w-xs">
                      {currentFile.name}
                    </p>

                    <p className="text-sm text-gray-500">
                      {formatFileSize(currentFile.size)}
                    </p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleRemove(index)}
                  disabled={isLoading}
                  className="p-2 hover:bg-gray-200 rounded-full transition-colors disabled:opacity-50"
                  aria-label={`Remove ${currentFile.name}`}
                >
                  <X className="h-5 w-5 text-gray-600" />
                </button>
              </div>
            ))}
          </div>

          {/* Add More PDFs */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading}
            className="w-full border border-dashed border-gray-300 rounded-lg py-3 text-sm text-gray-600 hover:border-primary-500 hover:text-primary-600 transition-colors disabled:opacity-50"
          >
            + Add more PDFs
          </button>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 text-red-700 text-sm p-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Action Button */}
      {files.length > 0 && (
        <Button
          onClick={handleUpload}
          className="w-full"
          isLoading={isLoading}
          disabled={isLoading}
        >
          <Upload className="h-4 w-4 mr-2" />

          {isLoading
            ? "Processing PDFs..."
            : `Process ${files.length} ${
                files.length === 1 ? "PDF" : "PDFs"
              }`}
        </Button>
      )}

      {isLoading && (
        <LoadingSpinner
          text={`Extracting information from ${files.length} ${
            files.length === 1 ? "PDF" : "PDFs"
          }...`}
        />
      )}
    </div>
  );
}
