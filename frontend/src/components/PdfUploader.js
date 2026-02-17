import { useState, useEffect, useRef, useCallback } from "react";
import { Upload, X, FileText, Trash2, CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from "../components/ui/dialog";
import { ScrollArea } from "../components/ui/scroll-area";
import { uploadPdf, getDocuments, deleteDocument } from "../services/api";

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

export const PdfUploader = ({ open, onOpenChange }) => {
    const [documents, setDocuments] = useState([]);
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState(null);
    const [dragActive, setDragActive] = useState(false);
    const fileInputRef = useRef(null);

    // Fetch existing documents when dialog opens
    useEffect(() => {
        if (open) {
            fetchDocuments();
        }
    }, [open]);

    const fetchDocuments = async () => {
        try {
            const docs = await getDocuments();
            setDocuments(docs);
        } catch (err) {
            console.error("Failed to fetch documents:", err);
        }
    };

    const handleFile = useCallback(async (file) => {
        setUploadError(null);

        if (!file.name.toLowerCase().endsWith(".pdf")) {
            setUploadError("Only PDF files are supported");
            return;
        }
        if (file.size > MAX_FILE_SIZE) {
            setUploadError("File too large (max 10 MB)");
            return;
        }

        setUploading(true);
        try {
            const result = await uploadPdf(file);
            setDocuments((prev) => [...prev, result]);
        } catch (err) {
            const msg =
                err.response?.data?.detail || err.message || "Upload failed";
            setUploadError(msg);
        } finally {
            setUploading(false);
        }
    }, []);

    const handleDelete = useCallback(async (docId) => {
        try {
            await deleteDocument(docId);
            setDocuments((prev) => prev.filter((d) => d.doc_id !== docId));
        } catch (err) {
            console.error("Delete failed:", err);
        }
    }, []);

    const handleDrop = useCallback(
        (e) => {
            e.preventDefault();
            setDragActive(false);
            const file = e.dataTransfer.files[0];
            if (file) handleFile(file);
        },
        [handleFile]
    );

    const handleDragOver = (e) => {
        e.preventDefault();
        setDragActive(true);
    };

    const handleDragLeave = () => setDragActive(false);

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2 text-slate-900">
                        <FileText className="h-5 w-5 text-blue-600" />
                        Upload Property Documents
                    </DialogTitle>
                    <DialogDescription className="text-slate-500">
                        Upload PDF brochures so Priya can answer questions about your
                        properties.
                    </DialogDescription>
                </DialogHeader>

                {/* Drop zone */}
                <div
                    data-testid="pdf-drop-zone"
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onClick={() => fileInputRef.current?.click()}
                    className={`
            mt-2 flex flex-col items-center justify-center rounded-xl border-2 border-dashed
            px-6 py-8 cursor-pointer transition-colors
            ${dragActive
                            ? "border-blue-500 bg-blue-50"
                            : "border-slate-300 hover:border-blue-400 hover:bg-slate-50"
                        }
            ${uploading ? "opacity-50 pointer-events-none" : ""}
          `}
                >
                    {uploading ? (
                        <Loader2 className="h-8 w-8 text-blue-500 animate-spin" />
                    ) : (
                        <Upload className="h-8 w-8 text-slate-400" />
                    )}
                    <p className="mt-2 text-sm text-slate-600 text-center">
                        {uploading
                            ? "Uploading & processing..."
                            : "Drag & drop a PDF here, or click to browse"}
                    </p>
                    <p className="text-xs text-slate-400 mt-1">PDF only, max 10 MB</p>
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf"
                        className="hidden"
                        onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) handleFile(file);
                            e.target.value = ""; // allow re-upload of same file
                        }}
                    />
                </div>

                {/* Error */}
                {uploadError && (
                    <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
                        <X className="h-4 w-4 shrink-0" />
                        {uploadError}
                    </div>
                )}

                {/* Document list */}
                {documents.length > 0 && (
                    <div className="mt-2">
                        <p className="text-xs font-medium text-slate-500 mb-2 uppercase tracking-wider">
                            Uploaded Documents ({documents.length})
                        </p>
                        <ScrollArea className="max-h-48">
                            <div className="space-y-2">
                                {documents.map((doc) => (
                                    <div
                                        key={doc.doc_id}
                                        className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2.5"
                                    >
                                        <div className="flex items-center gap-2 min-w-0">
                                            <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                                            <div className="min-w-0">
                                                <p className="text-sm text-slate-800 truncate">
                                                    {doc.filename}
                                                </p>
                                                <p className="text-xs text-slate-400">
                                                    {doc.num_chunks} chunks indexed
                                                </p>
                                            </div>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-7 w-7 text-slate-400 hover:text-red-500"
                                            onClick={() => handleDelete(doc.doc_id)}
                                        >
                                            <Trash2 className="h-3.5 w-3.5" />
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        </ScrollArea>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
};
