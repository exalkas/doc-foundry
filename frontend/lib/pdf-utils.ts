/**
 * Client-side PDF utilities for page counting and preview
 */

/**
 * Get page count from a PDF file
 * @param file - PDF file object
 * @returns Promise resolving to page count
 */
export async function getPdfPageCount(file: File): Promise<number> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = async (e) => {
      try {
        const arrayBuffer = e.target?.result as ArrayBuffer;
        if (!arrayBuffer) {
          reject(new Error("Failed to read file"));
          return;
        }

        // Use PDF.js to count pages
        // Dynamically import pdfjs-dist to avoid SSR issues
        const pdfjsLib = await import("pdfjs-dist");

        // Set worker source
        pdfjsLib.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;

        const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
        const pdf = await loadingTask.promise;
        resolve(pdf.numPages);
      } catch (error) {
        console.error("Error counting PDF pages:", error);
        // Fallback: try to parse as PDF and count pages using regex
        try {
          const text = await file.text();
          const pageMatches = text.match(/\/Type[\s]*\/Page[^s]/g);
          const count = pageMatches ? pageMatches.length : 1;
          resolve(count);
        } catch (fallbackError) {
          // If all else fails, assume 1 page
          resolve(1);
        }
      }
    };

    reader.onerror = () => {
      reject(new Error("Failed to read file"));
    };

    reader.readAsArrayBuffer(file);
  });
}

/**
 * Get page count for any file type (PDF or image)
 * @param file - File object
 * @returns Promise resolving to page count (1 for images, actual count for PDFs)
 */
export async function getFilePageCount(file: File): Promise<number> {
  const ext = file.name.split(".").pop()?.toLowerCase();

  if (ext === "pdf") {
    return getPdfPageCount(file);
  }

  // Images are always 1 page
  if (["png", "jpg", "jpeg", "tiff", "tif", "bmp", "gif"].includes(ext || "")) {
    return Promise.resolve(1);
  }

  // Unknown file type, assume 1 page
  return Promise.resolve(1);
}
