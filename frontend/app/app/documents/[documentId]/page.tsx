"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Spinner } from "@/components/ui/spinner";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  FileJson,
  FileSpreadsheet,
  RotateCcw,
  Sparkles,
  Eye,
  Play,
  Wand2,
  Edit,
  X,
  FileCode2,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useParams } from "next/navigation";
import { get, post, patch } from "@/lib/api-client";
import type {
  Document,
  ExtractionResult,
  ExtractionLog,
  Template,
} from "@/lib/types";
import { ROUTES } from "@/lib/constants";
import { useToast } from "@/hooks/use-toast";
import { getSuccessMessage, getErrorMessage } from "@/lib/notifications";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Info } from "lucide-react";
import {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
  useLayoutEffect,
} from "react";

// Helper function to format language code for display
function formatLanguageCode(langCode: string | undefined | null): string {
  if (!langCode) return "Not specified";

  // Language name mapping (common languages)
  const languageNames: Record<string, string> = {
    eng: "English",
    ell: "Greek",
    fra: "French",
    spa: "Spanish",
    deu: "German",
    ita: "Italian",
    por: "Portuguese",
    rus: "Russian",
    jpn: "Japanese",
    kor: "Korean",
    chi_sim: "Chinese (Simplified)",
    chi_tra: "Chinese (Traditional)",
    ara: "Arabic",
    hin: "Hindi",
    tur: "Turkish",
    pol: "Polish",
    nld: "Dutch",
    swe: "Swedish",
    nor: "Norwegian",
    dan: "Danish",
    fin: "Finnish",
    // ISO 639-1 codes
    en: "English",
    el: "Greek",
    fr: "French",
    es: "Spanish",
    de: "German",
    it: "Italian",
    pt: "Portuguese",
    ru: "Russian",
    ja: "Japanese",
    ko: "Korean",
    zh: "Chinese",
    ar: "Arabic",
    hi: "Hindi",
    tr: "Turkish",
    pl: "Polish",
    nl: "Dutch",
    sv: "Swedish",
    no: "Norwegian",
    da: "Danish",
    fi: "Finnish",
  };

  const code = langCode.toLowerCase();
  const name = languageNames[code];

  if (name) {
    return `${name} (${code})`;
  }

  // Handle multi-language codes (e.g., "eng+fra")
  if (code.includes("+")) {
    const codes = code.split("+").map((c) => c.trim());
    const names = codes.map((c) => languageNames[c] || c).join(", ");
    return `${names} (${code})`;
  }

  // Return uppercase code if no mapping found
  return code.toUpperCase();
}

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const documentId = params.documentId as string;

  const {
    data: documentData,
    isLoading,
    error,
  } = useQuery<{
    document: Document;
    extraction_result?: ExtractionResult;
    logs?: ExtractionLog[];
  }>({
    queryKey: ["document", documentId],
    queryFn: () => get(`/api/documents/${documentId}`),
    enabled: !!documentId,
    refetchInterval: (query) => {
      // Poll if document is still processing
      const data = query.state.data;
      return data?.document?.status === "processing" ||
        data?.document?.status === "pending"
        ? 3000
        : false;
    },
    retry: false, // Don't retry on 404 errors
  });

  const document = documentData?.document;

  // Extract results and logs from document data
  const extraction_result = documentData?.extraction_result;
  const logs = documentData?.logs || [];

  // Fetch OCR blocks
  type OCRBlock = {
    text: string;
    bbox: [number, number, number, number];
    bbox_pixels?: [number, number, number, number];
    confidence: number;
    page: number;
  };

  const { data: ocrBlocksData } = useQuery<{
    blocks: OCRBlock[];
  }>({
    queryKey: ["document", documentId, "ocr-blocks"],
    queryFn: () => get(`/api/documents/${documentId}/ocr-blocks`),
    enabled: !!documentId && !!document,
  });

  const ocrBlocks: OCRBlock[] =
    ocrBlocksData?.blocks ||
    (document?.raw_ocr_metadata?.blocks as OCRBlock[]) ||
    [];

  const retryMutation = useMutation({
    mutationFn: () => post(`/api/documents/${documentId}/retry`),
    onSuccess: () => {
      toast({
        variant: "success",
        title: "Document reprocessing started",
        description: "Document has been queued for reprocessing",
      });
      queryClient.invalidateQueries({ queryKey: ["document", documentId] });
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "update", "document"),
      });
    },
  });

  const retryWithAIMutation = useMutation({
    mutationFn: () => post(`/api/documents/${documentId}/retry-with-ai`),
    onSuccess: () => {
      toast({
        variant: "success",
        title: "AI extraction started",
        description: "Document has been queued for AI-powered extraction",
      });
      queryClient.invalidateQueries({ queryKey: ["document", documentId] });
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "update", "document"),
      });
    },
  });

  // Generate template with AI mutation
  const generateTemplateMutation = useMutation<
    { job_id: string; status: string; message: string },
    Error,
    {
      export_format?: string;
      template_name?: string;
      description?: string;
    }
  >({
    mutationFn: (data: {
      export_format?: string;
      template_name?: string;
      description?: string;
    }) =>
      post<{ job_id: string; status: string; message: string }>(
        `/api/documents/${documentId}/generate-template`,
        data
      ),
    onSuccess: (data) => {
      setAutoMatchMessage(null); // Clear auto-match message when user creates template
      setShowGenerateTemplateDialog(false); // Close dialog
      setTemplateName(""); // Reset form
      setTemplateDescription("");
      setExportFormat("json");
      toast({
        variant: "default",
        title: "Template generation started",
        description:
          "Template generation is in progress. You'll be notified when it completes.",
      });
      // Start polling for job status
      startJobPolling(data.job_id);
    },
    onError: (error) => {
      const errorMessage =
        getErrorMessage(error, "create", "template") ||
        "Failed to generate template";

      // Check if it's a template limit error
      if (
        errorMessage.toLowerCase().includes("template limit") ||
        errorMessage.toLowerCase().includes("exceeds plan limit")
      ) {
        setTemplateLimitError(errorMessage);
      } else {
        toast({
          variant: "destructive",
          title: "Error",
          description: errorMessage,
        });
      }
    },
  });

  // Job polling state
  const [pollingJobId, setPollingJobId] = useState<string | null>(null);
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(
    null
  );

  // Start polling for job status
  const startJobPolling = useCallback(
    (jobId: string) => {
      setPollingJobId(jobId);

      // Clear any existing polling
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }

      // Poll every 2 seconds
      const interval = setInterval(async () => {
        try {
          const jobStatus = await get<{
            job_id: string;
            status: string;
            type: string;
            template_id?: string;
            last_error?: string;
          }>(`/api/documents/jobs/${jobId}`);

          if (jobStatus.status === "succeeded") {
            clearInterval(interval);
            setPollingJobId(null);
            setPollingInterval(null);

            toast({
              variant: "success",
              title: "Template generated",
              description: "Template has been created successfully",
            });

            queryClient.invalidateQueries({
              queryKey: ["document", documentId],
            });
            queryClient.invalidateQueries({ queryKey: ["templates"] });
          } else if (jobStatus.status === "failed") {
            clearInterval(interval);
            setPollingJobId(null);
            setPollingInterval(null);

            toast({
              variant: "destructive",
              title: "Template generation failed",
              description:
                jobStatus.last_error || "Failed to generate template",
            });
          }
        } catch (error) {
          // Continue polling on error (job might not exist yet)
          console.error("Error polling job status:", error);
        }
      }, 2000);

      setPollingInterval(interval);
    },
    [pollingInterval, documentId, queryClient]
  );

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [pollingInterval]);

  // Fetch templates for manual selection
  const { data: templatesData } = useQuery<{
    templates: Template[];
    pagination: {
      page: number;
      page_size: number;
      total: number;
      total_pages: number;
    };
  }>({
    queryKey: ["templates"],
    queryFn: () => get("/api/templates"),
  });

  const templates = templatesData?.templates || [];

  const [isEditingFields, setIsEditingFields] = useState(false);
  const [editedJson, setEditedJson] = useState<Record<string, any>>({});
  const [templateLimitError, setTemplateLimitError] = useState<string | null>(
    null
  );
  const [autoMatchMessage, setAutoMatchMessage] = useState<string | null>(null);
  const [selectedPage, setSelectedPage] = useState<number>(1);
  const [hoveredBlock, setHoveredBlock] = useState<number | null>(null);
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);
  const [selectedTemplateForExtraction, setSelectedTemplateForExtraction] =
    useState<string | null>(null);
  const [showGenerateTemplateDialog, setShowGenerateTemplateDialog] =
    useState(false);
  const [templateName, setTemplateName] = useState("");
  const [templateDescription, setTemplateDescription] = useState("");
  const [exportFormat, setExportFormat] = useState<"json" | "csv" | "excel">(
    "json"
  );

  // Update edited JSON when extraction result changes
  useEffect(() => {
    if (extraction_result?.extracted_json) {
      setEditedJson(extraction_result.extracted_json);
    }
  }, [extraction_result]);

  // Auto-match template mutation
  const autoMatchMutation = useMutation({
    mutationFn: () =>
      post(`/api/documents/${documentId}/extract`, {
        auto_match: true,
      }),
    onSuccess: () => {
      setAutoMatchMessage(null); // Clear any previous messages
      toast({
        variant: "success",
        title: "Template matched",
        description: "Extraction started with auto-matched template",
      });
      queryClient.invalidateQueries({ queryKey: ["document", documentId] });
    },
    onError: (error) => {
      // Extract error message - check if it's a no-match scenario
      const errorMessage = getErrorMessage(error, "match", "template");
      const isNoMatch =
        errorMessage.toLowerCase().includes("no matching template") ||
        errorMessage.toLowerCase().includes("no templates available");

      if (isNoMatch) {
        // Store message to show in UI
        setAutoMatchMessage(errorMessage);
        // Show as informational toast, not an error
        toast({
          variant: "info",
          title: "No template match found",
          description: "Please select a template manually or create a new one",
        });
      } else {
        // For other errors, show as warning
        toast({
          variant: "warning",
          title: "Template matching issue",
          description: errorMessage,
        });
      }
    },
  });

  // Manual extraction mutation
  const extractMutation = useMutation({
    mutationFn: (templateId: string) =>
      post(`/api/documents/${documentId}/extract`, {
        template_id: templateId,
      }),
    onSuccess: () => {
      setAutoMatchMessage(null); // Clear auto-match message when user selects template
      toast({
        variant: "success",
        title: "Extraction started",
        description: "Document is being processed",
      });
      queryClient.invalidateQueries({ queryKey: ["document", documentId] });
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "extract", "document"),
      });
    },
  });

  // Save manual edits mutation
  const saveEditsMutation = useMutation({
    mutationFn: (json: Record<string, any>) =>
      patch(`/api/documents/${documentId}/extraction-result`, json),
    onSuccess: () => {
      toast({
        variant: "success",
        title: "Changes saved",
        description: "Extraction result updated successfully",
      });
      setIsEditingFields(false);
      queryClient.invalidateQueries({ queryKey: ["document", documentId] });
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: getErrorMessage(error, "save", "document"),
      });
    },
  });

  // Check if document has low confidence and can use AI retry
  const confidence = document?.raw_ocr_metadata?.confidence || 1.0;
  const canRetryWithAI = confidence < 0.8 && document?.status === "completed";

  // Initialize selected page to first page with OCR blocks
  useEffect(() => {
    if (ocrBlocks.length > 0 && selectedPage === 1) {
      const firstPage = Math.min(...ocrBlocks.map((b) => b.page));
      setSelectedPage(firstPage);
    }
  }, [ocrBlocks.length]);

  // Invalidate documents list if document is not found (404)
  useEffect(() => {
    if (
      error &&
      ((error as any)?.response?.status === 404 ||
        (error as any)?.status === 404)
    ) {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    }
  }, [error, queryClient]);

  const handleExport = async (format: "json" | "csv" | "excel") => {
    try {
      const response = await fetch(
        `/api/documents/${documentId}/export?format=${format}`,
        {
          credentials: "include",
        }
      );
      if (!response.ok) {
        throw new Error("Export failed");
      }

      // Parse JSON response to get download URL
      const exportInfo = await response.json();

      // Follow the download URL to get the actual file
      const downloadResponse = await fetch(exportInfo.download_url, {
        credentials: "include",
      });

      if (!downloadResponse.ok) {
        throw new Error("Download failed");
      }

      const blob = await downloadResponse.blob();
      const url = window.URL.createObjectURL(blob);
      const a = window.document.createElement("a");
      a.href = url;

      // Fix Excel extension
      const extension = format === "excel" ? "xlsx" : format;
      a.download = `${document?.file_name || "export"}.${extension}`;

      window.document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      window.document.body.removeChild(a);
    } catch (error) {
      toast({
        variant: "destructive",
        title: "Export failed",
        description:
          error instanceof Error ? error.message : "Failed to export document",
      });
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Spinner />
      </div>
    );
  }

  if (error || !document) {
    // Check if it's a 404 error
    const is404 =
      (error &&
        ((error as any)?.response?.status === 404 ||
          (error as any)?.status === 404)) ||
      (!document && !isLoading);

    return (
      <div className="space-y-6">
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink asChild>
                <Link href={ROUTES.DASHBOARD}>Dashboard</Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>Document</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>

        <Alert className="border-destructive/50 bg-destructive/10">
          <Info className="h-4 w-4 text-destructive" />
          <AlertTitle className="text-destructive">
            Document Not Found
          </AlertTitle>
          <AlertDescription className="space-y-4">
            <p>
              The document you're looking for could not be found. It may have
              been deleted, moved to a different workspace, or the link may be
              incorrect.
            </p>
            <div className="flex gap-2">
              <Button asChild>
                <Link href={ROUTES.DASHBOARD}>Go to Dashboard</Link>
              </Button>
              <Button variant="outline" onClick={() => router.back()}>
                Go Back
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  // OCR Preview Component
  function OCRPreview({
    documentId,
    document,
    ocrBlocks,
    selectedPage,
    setSelectedPage,
    hoveredBlock,
    setHoveredBlock,
  }: {
    documentId: string;
    document: Document;
    ocrBlocks: OCRBlock[];
    selectedPage: number;
    setSelectedPage: (page: number) => void;
    hoveredBlock: number | null;
    setHoveredBlock: (index: number | null) => void;
  }) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const imageRef = useRef<HTMLImageElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const scrollAreaRef = useRef<HTMLDivElement>(null);
    const hoveredBlockRef = useRef<number | null>(null);
    const [imageLoaded, setImageLoaded] = useState(false);
    const [imageError, setImageError] = useState(false);
    const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
    const canvasSizeRef = useRef({ width: 0, height: 0 });
    const animationFrameRef = useRef<number | null>(null);
    const redrawCanvasRef = useRef<() => void>(() => {});

    const pages = Array.from(new Set(ocrBlocks.map((b) => b.page))).sort();
    const pageBlocks = useMemo(
      () => ocrBlocks.filter((b) => b.page === selectedPage),
      [ocrBlocks, selectedPage]
    );

    // Memoize block list items to prevent re-renders
    const blockListItems = useMemo(() => {
      return pageBlocks.map((block, index) => {
        const blockKey = `${selectedPage}-${index}-${
          block.text?.substring(0, 20) || "empty"
        }-${block.bbox?.join("-") || ""}`;
        return { block, index, blockKey };
      });
    }, [pageBlocks, selectedPage]);

    // Get image URL
    const imageUrl =
      document.file_type === "application/pdf"
        ? `/api/documents/${documentId}/file?page=${selectedPage}`
        : `/api/documents/${documentId}/file`;

    // Function to redraw canvas - can be called directly without state updates
    const redrawCanvas = useCallback(() => {
      if (!canvasRef.current || !imageRef.current || !imageLoaded) return;

      const canvas = canvasRef.current;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const img = imageRef.current;
      const newWidth = img.offsetWidth;
      const newHeight = img.offsetHeight;

      // Only resize canvas if dimensions changed
      if (
        canvasSizeRef.current.width !== newWidth ||
        canvasSizeRef.current.height !== newHeight
      ) {
        canvas.width = newWidth;
        canvas.height = newHeight;
        canvasSizeRef.current = { width: newWidth, height: newHeight };
      }

      // Cancel any pending animation frame
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }

      // Use requestAnimationFrame for smooth updates
      animationFrameRef.current = requestAnimationFrame(() => {
        if (!canvasRef.current || !ctx) return;

        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw bounding boxes
        pageBlocks.forEach((block, index) => {
          // Use ref for immediate updates (primary source of truth)
          const isHovered = hoveredBlockRef.current === index;
          const bbox = block.bbox_pixels || block.bbox;

          if (!bbox || bbox.length < 4) return;

          let x: number, y: number, width: number, height: number;

          if (block.bbox_pixels) {
            // Use pixel coordinates directly
            [x, y, width, height] = bbox;
          } else {
            // Convert normalized coordinates to pixels
            x = bbox[0] * canvas.width;
            y = bbox[1] * canvas.height;
            width = (bbox[2] - bbox[0]) * canvas.width;
            height = (bbox[3] - bbox[1]) * canvas.height;
          }

          // Determine color based on confidence
          let color = "rgba(239, 68, 68, 0.3)"; // red - low confidence
          let borderColor = "rgb(239, 68, 68)";
          if (block.confidence >= 0.8) {
            color = "rgba(34, 197, 94, 0.3)"; // green - high confidence
            borderColor = "rgb(34, 197, 94)";
          } else if (block.confidence >= 0.6) {
            color = "rgba(234, 179, 8, 0.3)"; // yellow - medium confidence
            borderColor = "rgb(234, 179, 8)";
          }

          // Draw filled rectangle
          ctx.fillStyle = isHovered ? color.replace("0.3", "0.5") : color;
          ctx.fillRect(x, y, width, height);

          // Draw border
          ctx.strokeStyle = borderColor;
          ctx.lineWidth = isHovered ? 3 : 2;
          ctx.strokeRect(x, y, width, height);

          // Draw text label on hover
          if (isHovered && block.text) {
            ctx.fillStyle = "rgba(0, 0, 0, 0.8)";
            ctx.font = "12px sans-serif";
            const text = `${block.text.substring(0, 30)}${
              block.text.length > 30 ? "..." : ""
            } (${(block.confidence * 100).toFixed(0)}%)`;
            const textMetrics = ctx.measureText(text);
            const textX = x;
            const textY = y - 5;

            // Draw background for text
            ctx.fillStyle = "rgba(255, 255, 255, 0.9)";
            ctx.fillRect(textX - 4, textY - 16, textMetrics.width + 8, 18);

            // Draw text
            ctx.fillStyle = "rgb(0, 0, 0)";
            ctx.fillText(text, textX, textY);
          }
        });
      });
    }, [pageBlocks, imageLoaded]);

    // Store redraw function in ref for direct access
    redrawCanvasRef.current = redrawCanvas;

    // Draw bounding boxes on canvas - triggered by pageBlocks, imageLoaded, or selectedPage changes
    useEffect(() => {
      redrawCanvas();
      return () => {
        if (animationFrameRef.current) {
          cancelAnimationFrame(animationFrameRef.current);
        }
      };
    }, [redrawCanvas, imageSize, selectedPage, documentId]);

    // Handle image load
    const handleImageLoad = () => {
      if (imageRef.current) {
        setImageSize({
          width: imageRef.current.offsetWidth,
          height: imageRef.current.offsetHeight,
        });
        setImageLoaded(true);
        setImageError(false);
      }
    };

    // Handle mouse move to detect hover - uses refs to avoid re-renders
    const handleMouseMove = useCallback(
      (e: React.MouseEvent<HTMLDivElement>) => {
        if (!canvasRef.current || !imageRef.current || !imageLoaded) return;

        const rect = canvasRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Find which block is being hovered
        let hoveredIndex: number | null = null;
        pageBlocks.forEach((block, index) => {
          const bbox = block.bbox_pixels || block.bbox;
          if (!bbox || bbox.length < 4) return;

          let bx: number, by: number, bw: number, bh: number;
          if (block.bbox_pixels) {
            [bx, by, bw, bh] = bbox;
          } else {
            bx = bbox[0] * canvasRef.current!.width;
            by = bbox[1] * canvasRef.current!.height;
            bw = (bbox[2] - bbox[0]) * canvasRef.current!.width;
            bh = (bbox[3] - bbox[1]) * canvasRef.current!.height;
          }

          if (x >= bx && x <= bx + bw && y >= by && y <= by + bh) {
            hoveredIndex = index;
          }
        });

        // Only update ref and redraw if hovered block changed
        if (hoveredIndex !== hoveredBlockRef.current) {
          hoveredBlockRef.current = hoveredIndex;
          // Trigger canvas redraw directly without state update
          redrawCanvasRef.current();
        }
      },
      [pageBlocks, imageLoaded]
    );

    const handleMouseLeave = useCallback(() => {
      if (hoveredBlockRef.current !== null) {
        hoveredBlockRef.current = null;
        // Trigger canvas redraw directly without state update
        redrawCanvasRef.current();
      }
    }, []);

    return (
      <div className="space-y-4">
        {/* Page selector */}
        {pages.length > 1 && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Page:</span>
            <Select
              value={selectedPage.toString()}
              onValueChange={(value) => setSelectedPage(parseInt(value))}
            >
              <SelectTrigger className="w-[120px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {pages.map((page) => (
                  <SelectItem key={page} value={page.toString()}>
                    Page {page}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="text-xs text-muted-foreground">
              {pageBlocks.length} text block{pageBlocks.length !== 1 ? "s" : ""}
            </span>
          </div>
        )}

        {/* Image with overlay */}
        <div
          ref={containerRef}
          className="relative border rounded-md overflow-auto bg-muted/20"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          style={{
            maxHeight: "600px",
            contain: "layout style",
          }}
        >
          {imageError ? (
            <div className="p-8 text-center text-muted-foreground">
              <p>Failed to load document image</p>
              <p className="text-xs mt-2">
                The document file may not be available or accessible.
              </p>
            </div>
          ) : (
            <>
              <img
                ref={imageRef}
                src={imageUrl}
                alt={`Document page ${selectedPage}`}
                className="max-w-full h-auto"
                onLoad={handleImageLoad}
                onError={() => setImageError(true)}
                style={{ display: imageLoaded ? "block" : "none" }}
              />
              {!imageLoaded && !imageError && (
                <div className="p-8 text-center flex flex-col items-center">
                  <p className="text-sm text-muted-foreground mb-2">
                    Loading document image...
                  </p>
                  <Spinner />
                </div>
              )}
              <canvas
                ref={canvasRef}
                className="absolute top-0 left-0 pointer-events-none"
                style={{
                  display: imageLoaded ? "block" : "none",
                  willChange: "contents",
                  contain: "layout style paint",
                }}
              />
            </>
          )}
        </div>

        {/* Block list sidebar */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2" style={{ contain: "layout style" }}>
            <h4 className="text-sm font-semibold">Detected Text Blocks</h4>
            <div ref={scrollAreaRef} style={{ contain: "layout style" }}>
              <ScrollArea className="h-[300px] border rounded-md p-2">
                <div className="space-y-2">
                  {blockListItems.map(({ block, index, blockKey }) => {
                    // Use ref to track hover without causing re-renders
                    // Canvas updates happen directly via ref, no state updates needed
                    return (
                      <div
                        key={blockKey}
                        className="p-2 border rounded cursor-pointer transition-colors duration-150 bg-background hover:bg-accent/50"
                        onMouseEnter={() => {
                          // Update ref immediately (no re-render, no scroll reset)
                          hoveredBlockRef.current = index;
                          // Trigger canvas redraw directly
                          redrawCanvasRef.current();
                        }}
                        onMouseLeave={() => {
                          hoveredBlockRef.current = null;
                          // Trigger canvas redraw directly
                          redrawCanvasRef.current();
                        }}
                      >
                        <div className="text-sm font-medium break-words">
                          {block.text || (
                            <span className="text-muted-foreground italic">
                              (empty)
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Confidence:{" "}
                          <span
                            className={`font-medium ${
                              block.confidence >= 0.8
                                ? "text-green-600"
                                : block.confidence >= 0.6
                                ? "text-yellow-600"
                                : "text-red-600"
                            }`}
                          >
                            {(block.confidence * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </ScrollArea>
            </div>
          </div>

          {/* Legend */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold">Legend</h4>
            <div className="border rounded-md p-4 space-y-2 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-green-600 bg-green-600/30" />
                <span>
                  <span className="font-medium text-green-600">Green</span>:
                  High confidence (≥80%)
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-yellow-600 bg-yellow-600/30" />
                <span>
                  <span className="font-medium text-yellow-600">Yellow</span>:
                  Medium confidence (60-79%)
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-red-600 bg-red-600/30" />
                <span>
                  <span className="font-medium text-red-600">Red</span>: Low
                  confidence (&lt;60%)
                </span>
              </div>
              <div className="pt-2 border-t mt-2 text-muted-foreground">
                <p className="font-medium mb-1">Tips:</p>
                <ul className="list-disc list-inside space-y-1 ml-1">
                  <li>
                    Hover over blocks in the list to highlight them on the image
                  </li>
                  <li>
                    Hover over bounding boxes on the image to see text preview
                  </li>
                  <li>Click on blocks to select them</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb>
        <BreadcrumbList>
          {document?.project_id ? (
            <>
              <BreadcrumbItem>
                <BreadcrumbLink asChild>
                  <Link href={ROUTES.PROJECTS}>Projects</Link>
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbLink asChild>
                  <Link href={`${ROUTES.PROJECTS}/${document.project_id}`}>
                    Project
                  </Link>
                </BreadcrumbLink>
              </BreadcrumbItem>
            </>
          ) : (
            <BreadcrumbItem>
              <BreadcrumbLink asChild>
                <Link href={ROUTES.DOCUMENTS}>Documents</Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
          )}
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{document?.file_name || "Document"}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            {document.file_name}
          </h1>
          <p className="text-muted-foreground mt-2">
            Status: <span className="font-medium">{document.status}</span>
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {!extraction_result && document.raw_ocr_text && (
            <>
              <Button
                variant="default"
                onClick={() => setShowGenerateTemplateDialog(true)}
                disabled={
                  generateTemplateMutation.isPending || pollingJobId !== null
                }
              >
                <Sparkles className="mr-2 h-4 w-4" />
                {pollingJobId !== null
                  ? "Generating..."
                  : generateTemplateMutation.isPending
                  ? "Starting..."
                  : "Generate Template with AI"}
              </Button>
              <Button
                variant="outline"
                onClick={() => autoMatchMutation.mutate()}
                disabled={autoMatchMutation.isPending}
              >
                <Wand2 className="mr-2 h-4 w-4" />
                Auto-match Template
              </Button>
              <Button
                variant="outline"
                onClick={() => setShowTemplateDialog(true)}
                disabled={!templates || templates.length === 0}
              >
                <FileCode2 className="mr-2 h-4 w-4" />
                Select Template
              </Button>
            </>
          )}
          {extraction_result && (
            <>
              <Button variant="outline" onClick={() => handleExport("json")}>
                <FileJson className="mr-2 h-4 w-4" />
                Export JSON
              </Button>
              <Button variant="outline" onClick={() => handleExport("csv")}>
                <FileSpreadsheet className="mr-2 h-4 w-4" />
                Export CSV
              </Button>
              <Button variant="outline" onClick={() => handleExport("excel")}>
                <FileSpreadsheet className="mr-2 h-4 w-4" />
                Export Excel
              </Button>
            </>
          )}
          {document.status === "failed" && (
            <Button onClick={() => retryMutation.mutate()}>
              <RotateCcw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          )}
          {canRetryWithAI && (
            <Button
              variant="outline"
              onClick={() => retryWithAIMutation.mutate()}
              disabled={retryWithAIMutation.isPending}
            >
              <Sparkles className="mr-2 h-4 w-4" />
              Retry with AI
            </Button>
          )}
        </div>
      </div>

      {/* Auto-match informational message */}
      {autoMatchMessage && !extraction_result && document.raw_ocr_text && (
        <Alert className="border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950">
          <Info className="h-4 w-4 text-blue-600 dark:text-blue-400" />
          <AlertTitle className="text-blue-900 dark:text-blue-100">
            No template match found
          </AlertTitle>
          <AlertDescription className="text-blue-800 dark:text-blue-200">
            {autoMatchMessage}
            {templates && templates.length > 0 && (
              <span className="block mt-2">
                Please select a template from the dropdown above or create a new
                one using "Generate Template with AI".
              </span>
            )}
            {(!templates || templates.length === 0) && (
              <span className="block mt-2">
                Please create a template using "Generate Template with AI"
                button above.
              </span>
            )}
          </AlertDescription>
        </Alert>
      )}

      {/* Document Info - Horizontal Row */}
      <div className="flex flex-wrap items-center gap-4 py-4 border-b">
        <div>
          <p className="text-xs text-muted-foreground">Status</p>
          <span
            className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
              document.status === "completed"
                ? "bg-accent/10 text-accent"
                : document.status === "failed"
                ? "bg-destructive/10 text-destructive"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {document.status}
          </span>
        </div>
        {document.pages && (
          <div>
            <p className="text-xs text-muted-foreground">Pages</p>
            <p className="text-sm font-medium">{document.pages}</p>
          </div>
        )}
        {document.ocr_language && (
          <div>
            <p className="text-xs text-muted-foreground">Scanned language</p>
            <p className="text-sm font-medium">
              {formatLanguageCode(document.ocr_language)}
            </p>
          </div>
        )}
        <div>
          <p className="text-xs text-muted-foreground">Uploaded at</p>
          <p className="text-sm font-medium">
            {new Date(document.created_at).toLocaleString()}
          </p>
        </div>
        {document.template_id && (
          <div>
            <p className="text-xs text-muted-foreground">Template used</p>
            <p className="text-sm font-medium">-</p>
          </div>
        )}
        {document.last_error && (
          <div>
            <p className="text-xs text-destructive">Error</p>
            <p className="text-sm font-medium text-destructive">
              {document.last_error}
            </p>
          </div>
        )}
      </div>

      {/* Extraction View */}
      <Card>
        <CardHeader>
          <CardTitle>Extraction Results</CardTitle>
        </CardHeader>
        <CardContent>
          {extraction_result ? (
            <Tabs defaultValue="json" className="w-full">
              <div className="flex items-center justify-between mb-4">
                <TabsList>
                  <TabsTrigger value="json">JSON</TabsTrigger>
                  <TabsTrigger value="table">Table</TabsTrigger>
                  {(ocrBlocks.length > 0 || document?.raw_ocr_text) && (
                    <TabsTrigger value="ocr-preview">OCR Preview</TabsTrigger>
                  )}
                  {logs && logs.length > 0 && (
                    <TabsTrigger value="logs">Logs</TabsTrigger>
                  )}
                </TabsList>
                <div className="flex gap-2">
                  {!isEditingFields ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setIsEditingFields(true)}
                    >
                      <Edit className="mr-2 h-4 w-4" />
                      Edit Fields
                    </Button>
                  ) : (
                    <>
                      <Button
                        variant="default"
                        size="sm"
                        onClick={() => saveEditsMutation.mutate(editedJson)}
                        disabled={saveEditsMutation.isPending}
                      >
                        Save Changes
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setIsEditingFields(false);
                          setEditedJson(extraction_result.extracted_json);
                        }}
                      >
                        Cancel
                      </Button>
                    </>
                  )}
                </div>
              </div>
              <TabsContent value="json" className="mt-4">
                {isEditingFields ? (
                  <div className="space-y-4">
                    <textarea
                      className="w-full h-[400px] font-mono text-xs p-4 border border-input bg-background text-foreground rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                      value={JSON.stringify(editedJson, null, 2)}
                      onChange={(e) => {
                        try {
                          const parsed = JSON.parse(e.target.value);
                          setEditedJson(parsed);
                        } catch {
                          // Invalid JSON, keep as is
                        }
                      }}
                    />
                    <p className="text-xs text-muted-foreground">
                      Edit the JSON above and click "Save Changes" to update the
                      extraction result.
                    </p>
                  </div>
                ) : (
                  <ScrollArea className="h-[400px] w-full rounded-md border p-4">
                    <pre className="text-xs">
                      {JSON.stringify(
                        extraction_result.extracted_json,
                        null,
                        2
                      )}
                    </pre>
                  </ScrollArea>
                )}
              </TabsContent>
              <TabsContent value="table" className="mt-4">
                {isEditingFields ? (
                  <div className="space-y-4">
                    <div className="space-y-3">
                      {Object.entries(editedJson).map(([key, value], index) => (
                        <div key={key} className="flex gap-2 items-start">
                          <div className="flex-1">
                            <Input
                              value={key}
                              onChange={(e) => {
                                const newKey = e.target.value;
                                const newJson = { ...editedJson };
                                delete newJson[key];
                                newJson[newKey] = value;
                                setEditedJson(newJson);
                              }}
                              className="font-medium"
                              placeholder="Field name"
                            />
                          </div>
                          <div className="flex-1">
                            <Input
                              value={
                                typeof value === "object"
                                  ? JSON.stringify(value)
                                  : String(value)
                              }
                              onChange={(e) => {
                                const newValue = e.target.value;
                                // Try to parse as number, boolean, or keep as string
                                let parsedValue: any = newValue;
                                if (newValue === "true") parsedValue = true;
                                else if (newValue === "false")
                                  parsedValue = false;
                                else if (newValue === "null")
                                  parsedValue = null;
                                else if (
                                  !isNaN(Number(newValue)) &&
                                  newValue !== ""
                                ) {
                                  parsedValue = Number(newValue);
                                }
                                // Try to parse as JSON object/array
                                if (
                                  newValue.startsWith("{") ||
                                  newValue.startsWith("[")
                                ) {
                                  try {
                                    parsedValue = JSON.parse(newValue);
                                  } catch {
                                    // Keep as string if parsing fails
                                  }
                                }
                                setEditedJson({
                                  ...editedJson,
                                  [key]: parsedValue,
                                });
                              }}
                              placeholder="Field value"
                            />
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              const newJson = { ...editedJson };
                              delete newJson[key];
                              setEditedJson(newJson);
                            }}
                            className="text-destructive hover:text-destructive"
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const newKey = `field_${
                          Object.keys(editedJson).length + 1
                        }`;
                        setEditedJson({ ...editedJson, [newKey]: "" });
                      }}
                    >
                      + Add Field
                    </Button>
                    <p className="text-xs text-muted-foreground">
                      Edit field names and values above. Values are
                      automatically converted to the appropriate type (number,
                      boolean, object, or string).
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {Object.entries(extraction_result.extracted_json).map(
                      ([key, value]) => (
                        <div
                          key={key}
                          className="flex justify-between border-b pb-2"
                        >
                          <span className="font-medium">{key}</span>
                          <span className="text-muted-foreground">
                            {typeof value === "object"
                              ? JSON.stringify(value)
                              : String(value)}
                          </span>
                        </div>
                      )
                    )}
                  </div>
                )}
              </TabsContent>
              {(ocrBlocks.length > 0 || document?.raw_ocr_text) && (
                <TabsContent value="ocr-preview" className="mt-4">
                  {ocrBlocks.length > 0 ? (
                    <OCRPreview
                      documentId={documentId}
                      document={document}
                      ocrBlocks={ocrBlocks}
                      selectedPage={selectedPage}
                      setSelectedPage={setSelectedPage}
                      hoveredBlock={hoveredBlock}
                      setHoveredBlock={setHoveredBlock}
                    />
                  ) : (
                    <div className="p-8 text-center space-y-4">
                      <p className="text-muted-foreground">
                        OCR preview is not available for this document.
                      </p>
                      <p className="text-sm text-muted-foreground">
                        OCR text was extracted, but bounding box data is not
                        available. This may happen if:
                      </p>
                      <ul className="text-sm text-muted-foreground list-disc list-inside space-y-1">
                        <li>
                          The document was processed before OCR blocks were
                          implemented
                        </li>
                        <li>
                          The OCR engine didn't provide bounding box information
                        </li>
                      </ul>
                      <div className="pt-4 flex flex-col items-center gap-3">
                        <p className="text-sm text-muted-foreground">
                          You can view the extracted text in the "OCR Text" tab,
                          or retry extraction to generate bounding box data.
                        </p>
                        <Button
                          variant="outline"
                          onClick={() => retryMutation.mutate()}
                          disabled={retryMutation.isPending}
                        >
                          <RotateCcw className="mr-2 h-4 w-4" />
                          {retryMutation.isPending
                            ? "Retrying..."
                            : "Retry Extraction"}
                        </Button>
                      </div>
                    </div>
                  )}
                </TabsContent>
              )}
              {logs && logs.length > 0 && (
                <TabsContent value="logs" className="mt-4">
                  <ScrollArea className="h-[400px] w-full">
                    <div className="space-y-2">
                      {logs.map((log) => (
                        <div
                          key={log.id}
                          className={`text-xs p-2 rounded ${
                            log.level === "error"
                              ? "bg-destructive/10 text-destructive"
                              : log.level === "warning"
                              ? "bg-yellow-500/10 text-yellow-600"
                              : "bg-muted"
                          }`}
                        >
                          <span className="font-medium">
                            [{log.level.toUpperCase()}]
                          </span>{" "}
                          {new Date(log.created_at).toLocaleString()}:{" "}
                          {log.message}
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </TabsContent>
              )}
            </Tabs>
          ) : document.raw_ocr_text ? (
            <Tabs defaultValue="ocr" className="w-full">
              <TabsList>
                <TabsTrigger value="ocr">OCR Text</TabsTrigger>
                {(ocrBlocks.length > 0 || document?.raw_ocr_text) && (
                  <TabsTrigger value="ocr-preview">
                    <Eye className="mr-2 h-4 w-4" />
                    OCR Preview
                  </TabsTrigger>
                )}
                {logs && logs.length > 0 && (
                  <TabsTrigger value="logs">Logs</TabsTrigger>
                )}
              </TabsList>
              <TabsContent value="ocr" className="mt-4">
                <div className="space-y-4">
                  <div>
                    <p className="text-sm font-medium mb-2">Extracted Text</p>
                    <ScrollArea className="h-[400px] w-full rounded-md border p-4">
                      <pre className="text-xs whitespace-pre-wrap font-mono">
                        {document.raw_ocr_text}
                      </pre>
                    </ScrollArea>
                  </div>
                  {document.raw_ocr_metadata && (
                    <div className="text-xs text-muted-foreground space-y-1">
                      {document.raw_ocr_metadata.text_length && (
                        <p>
                          <span className="font-medium">Text length:</span>{" "}
                          {document.raw_ocr_metadata.text_length} characters
                        </p>
                      )}
                      {document.raw_ocr_metadata.word_count && (
                        <p>
                          <span className="font-medium">Word count:</span>{" "}
                          {document.raw_ocr_metadata.word_count} words
                        </p>
                      )}
                      {document.raw_ocr_metadata.confidence && (
                        <p>
                          <span className="font-medium">Confidence:</span>{" "}
                          {(document.raw_ocr_metadata.confidence * 100).toFixed(
                            1
                          )}
                          %
                        </p>
                      )}
                      {document.raw_ocr_metadata.page_count && (
                        <p>
                          <span className="font-medium">Pages:</span>{" "}
                          {document.raw_ocr_metadata.page_count}
                        </p>
                      )}
                      {document.raw_ocr_metadata.engine && (
                        <p>
                          <span className="font-medium">OCR Engine:</span>{" "}
                          {document.raw_ocr_metadata.engine}
                        </p>
                      )}
                    </div>
                  )}
                  {!document.template_id && (
                    <div className="rounded-md bg-yellow-500/10 border border-yellow-500/20 p-3">
                      <p className="text-sm text-yellow-600">
                        <span className="font-medium">Note:</span> This document
                        was processed without a template. Apply a template to
                        extract structured data from the OCR text.
                      </p>
                    </div>
                  )}
                </div>
              </TabsContent>
              {(ocrBlocks.length > 0 || document?.raw_ocr_text) && (
                <TabsContent value="ocr-preview" className="mt-4">
                  {ocrBlocks.length > 0 ? (
                    <OCRPreview
                      documentId={documentId}
                      document={document}
                      ocrBlocks={ocrBlocks}
                      selectedPage={selectedPage}
                      setSelectedPage={setSelectedPage}
                      hoveredBlock={hoveredBlock}
                      setHoveredBlock={setHoveredBlock}
                    />
                  ) : (
                    <div className="p-8 text-center space-y-4">
                      <p className="text-muted-foreground">
                        OCR preview is not available for this document.
                      </p>
                      <p className="text-sm text-muted-foreground">
                        OCR text was extracted, but bounding box data is not
                        available. This may happen if:
                      </p>
                      <ul className="text-sm text-muted-foreground list-disc list-inside space-y-1">
                        <li>
                          The document was processed before OCR blocks were
                          implemented
                        </li>
                        <li>
                          The OCR engine didn't provide bounding box information
                        </li>
                      </ul>
                      <div className="pt-4 flex flex-col items-center gap-3">
                        <p className="text-sm text-muted-foreground">
                          You can view the extracted text in the "OCR Text" tab,
                          or retry extraction to generate bounding box data.
                        </p>
                        <Button
                          variant="outline"
                          onClick={() => retryMutation.mutate()}
                          disabled={retryMutation.isPending}
                        >
                          <RotateCcw className="mr-2 h-4 w-4" />
                          {retryMutation.isPending
                            ? "Retrying..."
                            : "Retry Extraction"}
                        </Button>
                      </div>
                    </div>
                  )}
                </TabsContent>
              )}
              {logs && logs.length > 0 && (
                <TabsContent value="logs" className="mt-4">
                  <ScrollArea className="h-[400px] w-full">
                    <div className="space-y-2">
                      {logs.map((log) => (
                        <div
                          key={log.id}
                          className={`text-xs p-2 rounded ${
                            log.level === "error"
                              ? "bg-destructive/10 text-destructive"
                              : log.level === "warning"
                              ? "bg-yellow-500/10 text-yellow-600"
                              : "bg-muted"
                          }`}
                        >
                          <span className="font-medium">
                            [{log.level.toUpperCase()}]
                          </span>{" "}
                          {new Date(log.created_at).toLocaleString()}:{" "}
                          {log.message}
                          {log.metadata && (
                            <div className="mt-1 text-muted-foreground">
                              {JSON.stringify(log.metadata, null, 2)}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </TabsContent>
              )}
            </Tabs>
          ) : document.status === "processing" ||
            document.status === "pending" ? (
            <div className="text-center py-8">
              <p className="text-muted-foreground">Processing document...</p>
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-muted-foreground">
                No extraction result available
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Template Selection Dialog */}
      <Dialog open={showTemplateDialog} onOpenChange={setShowTemplateDialog}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Select Template</DialogTitle>
            <DialogDescription>
              Choose a template to extract structured data from this document
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 mt-4">
            {templates && templates.length > 0 ? (
              templates.map((template) => (
                <Card
                  key={template.id}
                  className="cursor-pointer hover:bg-accent transition-colors"
                  onClick={() => {
                    setSelectedTemplateForExtraction(template.id);
                    extractMutation.mutate(template.id);
                    setShowTemplateDialog(false);
                  }}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <p className="font-medium">{template.name}</p>
                        {template.description && (
                          <p className="text-sm text-muted-foreground mt-1">
                            {template.description}
                          </p>
                        )}
                        {template.project_id && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Project template
                          </p>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedTemplateForExtraction(template.id);
                          extractMutation.mutate(template.id);
                          setShowTemplateDialog(false);
                        }}
                        disabled={
                          extractMutation.isPending &&
                          selectedTemplateForExtraction === template.id
                        }
                      >
                        {extractMutation.isPending &&
                        selectedTemplateForExtraction === template.id
                          ? "Processing..."
                          : "Use"}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <FileCode2 className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p className="font-medium">No templates available</p>
                <p className="text-sm mt-2">
                  Create a template using "Generate Template with AI" or upload
                  one from the Templates page.
                </p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Generate Template with AI Dialog */}
      <Dialog
        open={showGenerateTemplateDialog}
        onOpenChange={setShowGenerateTemplateDialog}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Generate Template with AI</DialogTitle>
            <DialogDescription>
              Create a new extraction template from this document using AI. The
              template will analyze the document structure and create fields
              automatically.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label htmlFor="template-name">
                Template Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="template-name"
                placeholder="e.g., Invoice Template, Receipt Template"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="template-description">Description</Label>
              <Textarea
                id="template-description"
                placeholder="Optional description of what this template extracts..."
                value={templateDescription}
                onChange={(e) => setTemplateDescription(e.target.value)}
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="export-format">Default Export Format</Label>
              <Select
                value={exportFormat}
                onValueChange={(value: "json" | "csv" | "excel") =>
                  setExportFormat(value)
                }
              >
                <SelectTrigger id="export-format">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="json">JSON</SelectItem>
                  <SelectItem value="csv">CSV</SelectItem>
                  <SelectItem value="excel">Excel</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-6">
            <Button
              variant="outline"
              onClick={() => {
                setShowGenerateTemplateDialog(false);
                setTemplateName("");
                setTemplateDescription("");
                setExportFormat("json");
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (!templateName.trim()) {
                  toast({
                    variant: "destructive",
                    title: "Template name required",
                    description: "Please enter a template name",
                  });
                  return;
                }
                generateTemplateMutation.mutate({
                  template_name: templateName.trim(),
                  description: templateDescription.trim() || undefined,
                  export_format: exportFormat,
                });
              }}
              disabled={
                generateTemplateMutation.isPending || pollingJobId !== null
              }
            >
              {generateTemplateMutation.isPending || pollingJobId !== null
                ? "Generating..."
                : "Generate Template"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Template Limit Error Dialog */}
      <AlertDialog
        open={!!templateLimitError}
        onOpenChange={(open) => !open && setTemplateLimitError(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Template Limit Reached</AlertDialogTitle>
            <AlertDialogDescription className="space-y-4">
              <p>{templateLimitError}</p>
              <p className="text-sm text-muted-foreground">
                You've reached the maximum number of templates allowed on your
                current plan. To create more templates, you can:
              </p>
              <ul className="list-disc list-inside space-y-2 text-sm text-muted-foreground ml-2">
                <li>Delete an existing template to free up space</li>
                <li>Upgrade your plan to get more templates</li>
                <li>Use an existing template instead of creating a new one</li>
              </ul>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="flex-col sm:flex-row gap-2">
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                router.push(ROUTES.TEMPLATES);
                setTemplateLimitError(null);
              }}
              className="bg-secondary text-secondary-foreground hover:bg-secondary/80"
            >
              View Templates
            </AlertDialogAction>
            <AlertDialogAction
              onClick={() => {
                router.push(ROUTES.USAGE_BILLING);
                setTemplateLimitError(null);
              }}
            >
              Upgrade Plan
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
