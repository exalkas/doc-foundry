"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";

export interface Selection {
  id: string;
  x: number; // Normalized 0-1
  y: number; // Normalized 0-1
  width: number; // Normalized 0-1
  height: number; // Normalized 0-1
  page: number;
}

interface SelectionOverlayProps {
  imageWidth: number;
  imageHeight: number;
  page: number;
  selections: Selection[];
  onSelectionCreate?: (selection: Selection) => void;
  onSelectionUpdate?: (id: string, selection: Selection) => void;
  onSelectionDelete?: (id: string) => void;
  onSelectionClick?: (id: string) => void;
  selectedId?: string;
  className?: string;
  disabled?: boolean;
}

export function SelectionOverlay({
  imageWidth,
  imageHeight,
  page,
  selections,
  onSelectionCreate,
  onSelectionUpdate,
  onSelectionDelete,
  onSelectionClick,
  selectedId,
  className,
  disabled = false,
}: SelectionOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPos, setStartPos] = useState<{ x: number; y: number } | null>(
    null
  );
  const [currentRect, setCurrentRect] = useState<Selection | null>(null);
  const [imageTransform, setImageTransform] = useState<{
    scale: number;
    offsetX: number;
    offsetY: number;
    displayedWidth: number;
    displayedHeight: number;
  } | null>(null);

  // Filter selections for current page
  const pageSelections = selections.filter((s) => s.page === page);

  // Calculate image transform (scale and offset) based on actual displayed size
  useEffect(() => {
    const updateTransform = () => {
      if (!containerRef.current) return;

      // Use requestAnimationFrame to ensure DOM is updated
      requestAnimationFrame(() => {
        if (!containerRef.current) return;

        // Find the actual image element - it's in a sibling DocumentViewer component
        // Try multiple strategies to find the image
        let img: HTMLImageElement | null = null;

        // Strategy 1: Look in parent's children (DocumentViewer is a sibling)
        const parent = containerRef.current.parentElement;
        if (parent) {
          img = parent.querySelector("img");
        }

        // Strategy 2: If not found, look in the entire document (fallback)
        if (!img) {
          // Find the closest common ancestor and search from there
          const commonAncestor = containerRef.current.closest(".relative");
          if (commonAncestor) {
            img = commonAncestor.querySelector("img");
          }
        }

        if (!img || (img.complete === false && !img.naturalWidth)) return;

        const imgRect = img.getBoundingClientRect();
        const containerRect = containerRef.current.getBoundingClientRect();

        // Only proceed if we have valid dimensions
        if (imgRect.width === 0 || imgRect.height === 0) return;

        // The image's displayed size is imgRect.width x imgRect.height
        // Calculate scale factor based on actual displayed size vs natural size
        const scaleX = imgRect.width / imageWidth;
        const scaleY = imgRect.height / imageHeight;
        const scale = Math.min(scaleX, scaleY);

        // Calculate the displayed dimensions (maintaining aspect ratio)
        const displayedWidth = imageWidth * scale;
        const displayedHeight = imageHeight * scale;

        // Calculate offset: position of image relative to overlay container
        // getBoundingClientRect already accounts for scroll, transforms, and padding
        // So we just need the difference in viewport positions
        const offsetX = imgRect.left - containerRect.left;
        const offsetY = imgRect.top - containerRect.top;

        // Debug logging (remove in production)
        console.log("SelectionOverlay transform:", {
          imageWidth,
          imageHeight,
          imgRect: { width: imgRect.width, height: imgRect.height },
          containerRect: {
            width: containerRect.width,
            height: containerRect.height,
          },
          scale,
          offsetX,
          offsetY,
          displayedWidth,
          displayedHeight,
        });

        setImageTransform({
          scale,
          offsetX,
          offsetY,
          displayedWidth,
          displayedHeight,
        });
      });
    };

    // Helper to find the image element
    const findImage = () => {
      if (!containerRef.current) return null;
      const parent = containerRef.current.parentElement;
      if (parent) {
        return parent.querySelector("img");
      }
      const commonAncestor = containerRef.current.closest(".relative");
      if (commonAncestor) {
        return commonAncestor.querySelector("img");
      }
      return null;
    };

    // Initial update with a small delay to ensure image is rendered
    const timeoutId = setTimeout(updateTransform, 100);
    window.addEventListener("resize", updateTransform);

    // Update when image loads - use same detection strategy
    const img = findImage();
    if (img) {
      if (img.complete && img.naturalWidth > 0) {
        updateTransform();
      } else {
        img.addEventListener("load", updateTransform);
        img.addEventListener("error", () => {
          console.warn("SelectionOverlay: Image failed to load");
        });
      }
    }

    // Use ResizeObserver to detect when container or image size changes
    let resizeObserver: ResizeObserver | null = null;
    if (containerRef.current && window.ResizeObserver) {
      resizeObserver = new ResizeObserver(updateTransform);
      resizeObserver.observe(containerRef.current);
      const img = findImage();
      if (img) {
        resizeObserver.observe(img);
        // Also observe the image's parent containers that might affect positioning
        const imgParent = img.parentElement;
        if (imgParent) {
          resizeObserver.observe(imgParent);
        }
      }
    }

    return () => {
      clearTimeout(timeoutId);
      window.removeEventListener("resize", updateTransform);
      img?.removeEventListener("load", updateTransform);
      resizeObserver?.disconnect();
    };
  }, [imageWidth, imageHeight]);

  // Convert normalized coordinates to pixel coordinates (for drawing on canvas)
  const normalizedToPixels = useCallback(
    (x: number, y: number, width: number, height: number) => {
      if (!imageTransform) {
        return { x: 0, y: 0, width: 0, height: 0 };
      }
      return {
        x: x * imageTransform.displayedWidth + imageTransform.offsetX,
        y: y * imageTransform.displayedHeight + imageTransform.offsetY,
        width: width * imageTransform.displayedWidth,
        height: height * imageTransform.displayedHeight,
      };
    },
    [imageTransform]
  );

  // Convert pixel coordinates (from mouse) to normalized coordinates (0-1)
  const pixelsToNormalized = useCallback(
    (x: number, y: number, width: number, height: number) => {
      if (!imageTransform) {
        return { x: 0, y: 0, width: 0, height: 0 };
      }

      // Convert mouse coordinates relative to container to image coordinates
      const imgX = (x - imageTransform.offsetX) / imageTransform.scale;
      const imgY = (y - imageTransform.offsetY) / imageTransform.scale;
      const imgWidth = width / imageTransform.scale;
      const imgHeight = height / imageTransform.scale;

      // Normalize to 0-1
      return {
        x: imgX / imageWidth,
        y: imgY / imageHeight,
        width: imgWidth / imageWidth,
        height: imgHeight / imageHeight,
      };
    },
    [imageTransform, imageWidth, imageHeight]
  );

  // Get mouse position relative to container
  const getMousePos = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement> | MouseEvent) => {
      if (!containerRef.current) return { x: 0, y: 0 };
      const rect = containerRef.current.getBoundingClientRect();
      return {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      };
    },
    []
  );

  // Handle mouse down - start drawing
  const handleMouseDown = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (disabled || !imageTransform) return;
      e.preventDefault();
      const pos = getMousePos(e);
      setIsDrawing(true);
      setStartPos(pos);
    },
    [disabled, getMousePos, imageTransform]
  );

  // Handle mouse move - update rectangle while drawing
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement> | MouseEvent) => {
      if (!isDrawing || !startPos || disabled) return;
      const pos = getMousePos(e);
      const x = Math.min(startPos.x, pos.x);
      const y = Math.min(startPos.y, pos.y);
      const width = Math.abs(pos.x - startPos.x);
      const height = Math.abs(pos.y - startPos.y);

      // Only create rectangle if it's large enough
      if (width > 5 && height > 5) {
        const normalized = pixelsToNormalized(x, y, width, height);
        setCurrentRect({
          id: "temp",
          x: normalized.x,
          y: normalized.y,
          width: normalized.width,
          height: normalized.height,
          page,
        });
      }
    },
    [isDrawing, startPos, disabled, getMousePos, pixelsToNormalized, page]
  );

  // Handle mouse up - finish drawing
  const handleMouseUp = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement> | MouseEvent) => {
      if (!isDrawing || !startPos || disabled) return;
      const pos = getMousePos(e);
      const x = Math.min(startPos.x, pos.x);
      const y = Math.min(startPos.y, pos.y);
      const width = Math.abs(pos.x - startPos.x);
      const height = Math.abs(pos.y - startPos.y);

      // Only create selection if it's large enough
      if (width > 5 && height > 5) {
        const normalized = pixelsToNormalized(x, y, width, height);
        const selection: Selection = {
          id: `selection-${Date.now()}`,
          x: normalized.x,
          y: normalized.y,
          width: normalized.width,
          height: normalized.height,
          page,
        };
        onSelectionCreate?.(selection);
      }

      setIsDrawing(false);
      setStartPos(null);
      setCurrentRect(null);
    },
    [
      isDrawing,
      startPos,
      disabled,
      getMousePos,
      pixelsToNormalized,
      page,
      onSelectionCreate,
    ]
  );

  // Global mouse move/up handlers for drawing outside canvas
  useEffect(() => {
    if (!isDrawing) return;

    const handleGlobalMouseMove = (e: MouseEvent) => {
      handleMouseMove(e);
    };

    const handleGlobalMouseUp = (e: MouseEvent) => {
      handleMouseUp(e);
    };

    window.addEventListener("mousemove", handleGlobalMouseMove);
    window.addEventListener("mouseup", handleGlobalMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleGlobalMouseMove);
      window.removeEventListener("mouseup", handleGlobalMouseUp);
    };
  }, [isDrawing, handleMouseMove, handleMouseUp]);

  // Draw selections on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || !imageTransform) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set canvas size to match container
    const rect = container.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw all selections
    pageSelections.forEach((selection) => {
      const pixels = normalizedToPixels(
        selection.x,
        selection.y,
        selection.width,
        selection.height
      );
      const isSelected = selection.id === selectedId;

      // Draw rectangle
      ctx.strokeStyle = isSelected ? "#3b82f6" : "#10b981";
      ctx.lineWidth = 2;
      ctx.setLineDash(isSelected ? [] : [5, 5]);
      ctx.strokeRect(pixels.x, pixels.y, pixels.width, pixels.height);

      // Fill with semi-transparent color
      ctx.fillStyle = isSelected
        ? "rgba(59, 130, 246, 0.1)"
        : "rgba(16, 185, 129, 0.1)";
      ctx.fillRect(pixels.x, pixels.y, pixels.width, pixels.height);
    });

    // Draw current rectangle being drawn
    if (currentRect) {
      const pixels = normalizedToPixels(
        currentRect.x,
        currentRect.y,
        currentRect.width,
        currentRect.height
      );
      ctx.strokeStyle = "#3b82f6";
      ctx.lineWidth = 2;
      ctx.setLineDash([]);
      ctx.strokeRect(pixels.x, pixels.y, pixels.width, pixels.height);
      ctx.fillStyle = "rgba(59, 130, 246, 0.2)";
      ctx.fillRect(pixels.x, pixels.y, pixels.width, pixels.height);
    }
  }, [
    pageSelections,
    currentRect,
    selectedId,
    normalizedToPixels,
    imageTransform,
  ]);

  // Check if point is inside a selection
  const getSelectionAtPoint = useCallback(
    (x: number, y: number): Selection | null => {
      if (!imageTransform) return null;

      // Convert mouse coordinates to normalized coordinates
      const normalized = pixelsToNormalized(x, y, 0, 0);
      const normalizedX = normalized.x;
      const normalizedY = normalized.y;

      for (const selection of pageSelections) {
        if (
          normalizedX >= selection.x &&
          normalizedX <= selection.x + selection.width &&
          normalizedY >= selection.y &&
          normalizedY <= selection.y + selection.height
        ) {
          return selection;
        }
      }
      return null;
    },
    [pageSelections, pixelsToNormalized, imageTransform]
  );

  // Handle click on selection
  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (disabled || isDrawing) return;
      const pos = getMousePos(e);
      const selection = getSelectionAtPoint(pos.x, pos.y);
      if (selection) {
        onSelectionClick?.(selection.id);
      }
    },
    [disabled, isDrawing, getMousePos, getSelectionAtPoint, onSelectionClick]
  );

  return (
    <div
      ref={containerRef}
      className={cn("absolute inset-0 pointer-events-none", className)}
    >
      <canvas
        ref={canvasRef}
        className={cn(
          "absolute inset-0 w-full h-full pointer-events-auto",
          disabled || !imageTransform
            ? "cursor-not-allowed"
            : "cursor-crosshair"
        )}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onClick={handleClick}
      />
      {!imageTransform && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/5 pointer-events-none">
          <p className="text-sm text-muted-foreground">Loading overlay...</p>
        </div>
      )}
    </div>
  );
}
