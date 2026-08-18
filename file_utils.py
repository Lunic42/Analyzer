"""
Uploaded-file text extraction. Real parsing of whatever the user actually
uploads — no placeholder/demo text.
"""
import io


def extract_text_from_upload(uploaded_file):
    """
    Extract plain text from a Streamlit UploadedFile (.txt, .pdf, or .docx).
    Returns (text, error). error is None on success.
    """
    name = uploaded_file.name.lower()
    data = uploaded_file.getvalue()

    try:
        if name.endswith(".txt"):
            return data.decode("utf-8", errors="replace"), None

        if name.endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            pages_text = [(page.extract_text() or "") for page in reader.pages]
            text = "\n".join(pages_text).strip()
            if not text:
                return "", "Couldn't extract text from this PDF — it may be a scanned image with no text layer."
            return text, None

        if name.endswith(".docx"):
            import docx
            document = docx.Document(io.BytesIO(data))
            text = "\n".join(p.text for p in document.paragraphs).strip()
            if not text:
                return "", "This DOCX file appears to have no readable text."
            return text, None

        ext = name.rsplit(".", 1)[-1] if "." in name else name
        return "", f"Unsupported file type: .{ext}. Please upload a .txt, .pdf, or .docx file."

    except Exception as e:
        return "", f"Couldn't read this file: {e}"