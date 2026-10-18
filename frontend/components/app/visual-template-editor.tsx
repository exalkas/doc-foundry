"use client";

import { useState, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { DocumentViewer } from "./document-viewer";
import { SelectionOverlay, type Selection } from "./selection-overlay";
import { useDocumentOCR } from "@/hooks/use-document-ocr";
import { get } from "@/lib/api-client";
import type { Document, OCRBlock } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Trash2, Plus, Upload, X } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface FieldDefinition {
  id: string;
  field_name: string;
  json_key: string;
  data_type: "string" | "number" | "date" | "boolean";
  required: boolean;
  default_value?: string;
  validation_rules?: string;
  selection_coordinates?: [number, number, number, number]; // [x, y, width, height]
  selection_page?: number;
  selection_method?: "visual" | "manual";
}

interface VisualTemplateEditorProps {
  templateId: string;
  fields: FieldDefinition[];
  onFieldsChange: (fields: FieldDefinition[]) => void;
  onDocumentSelect?: (documentId: string) => void;
}

export function VisualTemplateEditor({
  templateId,
  fields,
  onFieldsChange,
  onDocumentSelect,
}: VisualTemplateEditorProps) {
  // Don't allow visual editing for new templates (need template ID for OCR endpoint)
  if (templateId === "new") {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">
            Please save the template first before using the visual editor.
          </p>
        </CardContent>
      </Card>
    );
  }
  const { toast } = useToast();
  const [selectedDocumentId, setSelectedDocumentId] = useState<
    string | undefined
  >();
  const [currentPage, setCurrentPage] = useState(1);
  const [selections, setSelections] = useState<Selection[]>([]);
  const [selectedSelectionId, setSelectedSelectionId] = useState<
    string | undefined
  >();
  const [imageDimensions, setImageDimensions] = useState<{
    width: number;
    height: number;
  } | null>(null);
  const [showFieldDialog, setShowFieldDialog] = useState(false);
  const [pendingSelection, setPendingSelection] = useState<Selection | null>(
    null
  );
  const [newField, setNewField] = useState<Partial<FieldDefinition>>({
    field_name: "",
    json_key: "",
    data_type: "string",
    required: false,
  });

  // Fetch documents for selection
  const { data: documentsData } = useQuery<{ documents: Document[] }>({
    queryKey: ["documents", "completed"],
    queryFn: () => get("/api/documents?status=completed"),
  });

  const documents = documentsData?.documents || [];

  // Fetch OCR data for selected document
  const { data: ocrData, isLoading: ocrLoading } = useDocumentOCR(
    templateId,
    selectedDocumentId
  );

  // Load existing visual selections from fields
  useEffect(() => {
    const visualSelections: Selection[] = fields
      .filter((f) => f.selection_method === "visual" && f.selection_coordinates)
      .map((f) => ({
        id: f.id,
        x: f.selection_coordinates![0],
        y: f.selection_coordinates![1],
        width: f.selection_coordinates![2],
        height: f.selection_coordinates![3],
        page: f.selection_page || 1,
      }));
    setSelections(visualSelections);
  }, [fields]);

  // Set image dimensions from OCR data
  useEffect(() => {
    if (ocrData?.image_dimensions) {
      setImageDimensions(ocrData.image_dimensions);
    } else if (ocrData?.blocks && ocrData.blocks.length > 0) {
      // Estimate dimensions from OCR blocks
      const maxX = Math.max(
        ...ocrData.blocks.map((b) => b.bbox[0] + b.bbox[2])
      );
      const maxY = Math.max(
        ...ocrData.blocks.map((b) => b.bbox[1] + b.bbox[3])
      );
      // Use a reasonable default if we can't determine
      setImageDimensions({ width: 1200, height: 1600 });
    }
  }, [ocrData]);

  // Extract text from selection using OCR blocks
  const extractTextFromSelection = useCallback(
    (selection: Selection): string => {
      if (!ocrData?.blocks) return "";

      const x = selection.x;
      const y = selection.y;
      const width = selection.width;
      const height = selection.height;

      // Find blocks that overlap with selection
      const matchingBlocks: OCRBlock[] = [];
      for (const block of ocrData.blocks) {
        if (block.page !== selection.page) continue;

        const blockX = block.bbox[0];
        const blockY = block.bbox[1];
        const blockWidth = block.bbox[2];
        const blockHeight = block.bbox[3];
        const blockRight = blockX + blockWidth;
        const blockBottom = blockY + blockHeight;
        const selectionRight = x + width;
        const selectionBottom = y + height;

        // Check overlap
        if (
          blockX < selectionRight &&
          blockRight > x &&
          blockY < selectionBottom &&
          blockBottom > y
        ) {
          matchingBlocks.push(block);
        }
      }

      // Sort by position (top to bottom, left to right)
      matchingBlocks.sort((a, b) => {
        const aY = a.bbox[1];
        const bY = b.bbox[1];
        if (Math.abs(aY - bY) > 0.01) {
          return aY - bY;
        }
        return a.bbox[0] - b.bbox[0];
      });

      // Combine text
      return matchingBlocks.map((b) => b.text.trim()).join(" ");
    },
    [ocrData]
  );

  // Handle selection creation
  const handleSelectionCreate = useCallback(
    (selection: Selection) => {
      const extractedText = extractTextFromSelection(selection);
      setPendingSelection(selection);
      setNewField({
        field_name: extractedText.substring(0, 50) || "New Field",
        json_key:
          extractedText
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "_")
            .substring(0, 50) || "new_field",
        data_type: "string",
        required: false,
      });
      setShowFieldDialog(true);
    },
    [extractTextFromSelection]
  );

  // Create field from selection
  const handleCreateField = () => {
    if (!pendingSelection || !newField.field_name || !newField.json_key) {
      toast({
        variant: "destructive",
        title: "Error",
        description: "Please fill in field name and JSON key",
      });
      return;
    }

    const field: FieldDefinition = {
      id: `field-${Date.now()}`,
      field_name: newField.field_name,
      json_key: newField.json_key,
      data_type: newField.data_type || "string",
      required: newField.required || false,
      default_value: newField.default_value,
      validation_rules: newField.validation_rules,
      selection_coordinates: [
        pendingSelection.x,
        pendingSelection.y,
        pendingSelection.width,
        pendingSelection.height,
      ],
      selection_page: pendingSelection.page,
      selection_method: "visual",
    };

    onFieldsChange([...fields, field]);
    setSelections([...selections, pendingSelection]);
    setShowFieldDialog(false);
    setPendingSelection(null);
    setNewField({
      field_name: "",
      json_key: "",
      data_type: "string",
      required: false,
    });

    toast({
      variant: "success",
      title: "Field created",
      description: `Field "${field.field_name}" created from selection`,
    });
  };

  // Handle selection click
  const handleSelectionClick = (id: string) => {
    setSelectedSelectionId(id);
    const field = fields.find((f) => f.id === id);
    if (field) {
      // Could show field details or allow editing
    }
  };

  // Handle field deletion
  const handleDeleteField = (id: string) => {
    const updatedFields = fields.filter((f) => f.id !== id);
    const updatedSelections = selections.filter((s) => s.id !== id);
    onFieldsChange(updatedFields);
    setSelections(updatedSelections);
    if (selectedSelectionId === id) {
      setSelectedSelectionId(undefined);
    }
  };

  // Get document URL
  const getDocumentUrl = (document: Document): string => {
    // In production, this would be a proper file serving endpoint
    return `/api/documents/${document.id}/file`;
  };

  const selectedDocument = documents.find((d) => d.id === selectedDocumentId);

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Document Selection */}
      <Card>
        <CardHeader>
          <CardTitle>Select Sample Document</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Select
              value={selectedDocumentId}
              onValueChange={(value) => {
                setSelectedDocumentId(value);
                setCurrentPage(1);
                onDocumentSelect?.(value);
              }}
            >
              <SelectTrigger className="flex-1">
                <SelectValue placeholder="Choose a processed document" />
              </SelectTrigger>
              <SelectContent>
                {documents.map((doc) => (
                  <SelectItem key={doc.id} value={doc.id}>
                    {doc.file_name} {doc.pages ? `(${doc.pages} pages)` : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {selectedDocument && ocrLoading && (
            <p className="text-sm text-muted-foreground mt-2">
              Loading OCR data...
            </p>
          )}
          {selectedDocument && ocrData && (
            <p className="text-sm text-muted-foreground mt-2">
              Found {ocrData.blocks.length} OCR blocks across{" "}
              {ocrData.page_count} page(s)
            </p>
          )}
        </CardContent>
      </Card>

      {/* Visual Editor */}
      {selectedDocument && (
        <div className="flex-1 grid grid-cols-2 gap-4 min-h-0">
          {/* Document Viewer with Selection Overlay */}
          <Card className="flex flex-col min-h-0">
            <CardHeader>
              <CardTitle>Document</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 min-h-0 relative">
              <div className="relative w-full h-full">
                <DocumentViewer
                  documentUrl={getDocumentUrl(selectedDocument)}
                  documentType={selectedDocument.file_type}
                  pageCount={ocrData?.page_count || selectedDocument.pages || 1}
                  currentPage={currentPage}
                  onPageChange={setCurrentPage}
                  className="h-full"
                />
                {imageDimensions && ocrData && (
                  <SelectionOverlay
                    imageWidth={imageDimensions.width}
                    imageHeight={imageDimensions.height}
                    page={currentPage}
                    selections={selections}
                    onSelectionCreate={handleSelectionCreate}
                    onSelectionClick={handleSelectionClick}
                    selectedId={selectedSelectionId}
                    className="absolute inset-0"
                  />
                )}
              </div>
            </CardContent>
          </Card>

          {/* Fields Panel */}
          <Card className="flex flex-col min-h-0">
            <CardHeader>
              <CardTitle>Fields ({fields.length})</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 min-h-0">
              <ScrollArea className="h-full">
                <div className="space-y-2">
                  {fields.map((field) => (
                    <div
                      key={field.id}
                      className={`
                        p-3 border rounded-lg cursor-pointer
                        ${
                          selectedSelectionId === field.id
                            ? "border-blue-500 bg-blue-50 dark:bg-blue-950"
                            : ""
                        }
                      `}
                      onClick={() => {
                        setSelectedSelectionId(field.id);
                        if (field.selection_page) {
                          setCurrentPage(field.selection_page);
                        }
                      }}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="font-medium">{field.field_name}</div>
                          <div className="text-sm text-muted-foreground">
                            {field.json_key} ({field.data_type})
                          </div>
                          {field.selection_method === "visual" && (
                            <div className="text-xs text-muted-foreground mt-1">
                              Visual selection on page{" "}
                              {field.selection_page || 1}
                            </div>
                          )}
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteField(field.id);
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                  {fields.length === 0 && (
                    <div className="text-center py-8 text-muted-foreground">
                      <p>
                        No fields yet. Draw rectangles on the document to create
                        fields.
                      </p>
                    </div>
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Field Creation Dialog */}
      {showFieldDialog && pendingSelection && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Create Field from Selection</CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setShowFieldDialog(false);
                    setPendingSelection(null);
                  }}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Extracted Text Preview</Label>
                <div className="p-2 bg-muted rounded text-sm">
                  {extractTextFromSelection(pendingSelection) ||
                    "(No text found)"}
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="field-name">Field Name</Label>
                <Input
                  id="field-name"
                  value={newField.field_name || ""}
                  onChange={(e) =>
                    setNewField({ ...newField, field_name: e.target.value })
                  }
                  placeholder="e.g. Invoice Number"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="json-key">JSON Key</Label>
                <Input
                  id="json-key"
                  value={newField.json_key || ""}
                  onChange={(e) =>
                    setNewField({ ...newField, json_key: e.target.value })
                  }
                  placeholder="e.g. invoice_number"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="data-type">Data Type</Label>
                <Select
                  value={newField.data_type || "string"}
                  onValueChange={(value: FieldDefinition["data_type"]) =>
                    setNewField({ ...newField, data_type: value })
                  }
                >
                  <SelectTrigger id="data-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="string">String</SelectItem>
                    <SelectItem value="number">Number</SelectItem>
                    <SelectItem value="date">Date</SelectItem>
                    <SelectItem value="boolean">Boolean</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex gap-2">
                <Button onClick={handleCreateField} className="flex-1">
                  Create Field
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowFieldDialog(false);
                    setPendingSelection(null);
                  }}
                >
                  Cancel
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {!selectedDocument && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              Please select a processed document to start creating fields
              visually.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
