def extract_text(file_path):
    ext=file_path.lower().rsplit('.',1)[-1]
    if ext=='pdf':
        from pypdf import PdfReader
        return '\n'.join(page.extract_text() or '' for page in PdfReader(file_path).pages)
    if ext=='docx':
        from docx import Document
        return '\n'.join(p.text for p in Document(file_path).paragraphs)
    raise ValueError('Unsupported file type')
