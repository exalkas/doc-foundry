"use client";

import { useState, useEffect, useRef } from "react";
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface DocumentViewerProps {
  documentUrl: string;
  documentType: string;
  pageCount?: number;
  currentPage?: number;
  onPageChange?: (page: number) => void;
  className?: string;
}

export function DocumentViewer({
  documentUrl,
  documentType,
  pageCount = 1,
  currentPage: controlledPage,
  onPageChange,
  className,
}: DocumentViewerProps) {
  const [internalPage, setInternalPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [imageError, setImageError] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  const currentPage = controlledPage ?? internalPage;
  const isControlled = controlledPage !== undefined;

  const handlePageChange = (newPage: number) => {
    if (newPage < 1 || (pageCount > 0 && newPage > pageCount)) return;
    if (isControlled) {
      onPageChange?.(newPage);
    } else {
      setInternalPage(newPage);
    }
  };

  const handleZoomIn = () => {
    setZoom((prev) => Math.min(prev + 0.25, 3));
  };

  const handleZoomOut = () => {
    setZoom((prev) => Math.max(prev - 0.25, 0.5));
  };

  const handleRotate = () => {
    setRotation((prev) => (prev + 90) % 360);
  };

  const handleReset = () => {
    setZoom(1);
    setRotation(0);
  };

  // Check if document is a PDF (handle both "pdf" and "application/pdf" formats)
  const isPdf =
    documentType === "pdf" ||
    documentType === "application/pdf" ||
    documentType?.toLowerCase().includes("pdf");

  // Get image URL - for PDFs, backend converts to image
  const imageUrl = isPdf
    ? `${documentUrl}${
        documentUrl.includes("?") ? "&" : "?"
      }page=${currentPage}`
    : documentUrl;

  // Reset error when page changes
  useEffect(() => {
    setImageError(false);
  }, [currentPage, documentUrl]);

  return (
    <div className={cn("flex flex-col h-full", className)}>
      {/* Controls */}
      <div className="flex items-center justify-between p-2 border-b bg-background">
        <div className="flex items-center gap-2">
          {pageCount > 1 && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage <= 1}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm text-muted-foreground min-w-[80px] text-center">
                Page {currentPage} of {pageCount}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage >= pageCount}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleZoomOut}
            disabled={zoom <= 0.5}
            title="Zoom out"
          >
            <ZoomOut className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted-foreground min-w-[60px] text-center">
            {Math.round(zoom * 100)}%
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={handleZoomIn}
            disabled={zoom >= 3}
            title="Zoom in"
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRotate}
            title="Rotate"
          >
            <RotateCw className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleReset}
            title="Reset view"
          >
            Reset
          </Button>
        </div>
      </div>

      {/* Document Container */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto bg-gray-100 dark:bg-gray-900 p-4"
        style={{ position: "relative" }}
      >
        <div
          className="mx-auto"
          style={{
            transform: `scale(${zoom}) rotate(${rotation}deg)`,
            transformOrigin: "center center",
            transition: "transform 0.2s ease",
          }}
        >
          {imageError ? (
            <div className="flex items-center justify-center h-96 text-muted-foreground">
              <p>Failed to load document image</p>
            </div>
          ) : (
            <img
              ref={imageRef}
              src={imageUrl}
              alt={`Document page ${currentPage}`}
              className="max-w-full h-auto shadow-lg"
              onError={() => setImageError(true)}
              style={{
                display: "block",
                maxHeight: "none",
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
