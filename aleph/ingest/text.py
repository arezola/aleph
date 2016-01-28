import os
import logging
from tempfile import mkstemp

from lxml import html, etree
from lxml.html.clean import Cleaner
from extractors import extract_pdf, extract_image
from extractors import document_to_pdf, image_to_pdf

from aleph.core import archive
from aleph.model import db, Page, Document
from aleph.ingest.ingestor import Ingestor

log = logging.getLogger(__name__)


class TextIngestor(Ingestor):
    DOCUMENT_TYPE = Document.TYPE_TEXT

    def create_document(self, meta, type=None):
        document = super(TextIngestor, self).create_document(meta, type=type)
        document.delete_pages()
        return document

    def create_page(self, document, text, number=1):
        page = Page()
        page.document_id = document.id
        page.text = text
        page.number = number
        db.session.add(page)
        return page

    def store_pdf(self, meta, pdf_path, move=True):
        archive.archive_file(pdf_path, meta.pdf, move=move)


class PDFIngestor(TextIngestor):
    MIME_TYPES = ['application/pdf']
    EXTENSIONS = ['pdf']

    def extract_pdf(self, meta, pdf_path):
        data = extract_pdf(pdf_path)

        if not meta.has('author') and data.get('author'):
            meta['author'] = data.get('author')

        if not meta.has('title') and data.get('title'):
            meta.title = data.get('title')

        document = self.create_document(meta)
        for i, page in enumerate(data['pages']):
            self.create_page(document, page, number=i + 1)
        self.emit(document)

    def ingest(self, meta, local_path):
        self.extract_pdf(meta, local_path)


class DocumentIngestor(PDFIngestor):
    MIME_TYPES = ['application/msword', 'application/rtf', 'application/x-rtf',
                  'text/richtext', 'text/plain']
    EXTENSIONS = ['doc', 'docx', 'rtf', 'odt', 'sxw', 'dot', 'docm',
                  'hqx', 'pdb', 'txt']
    BASE_SCORE = 5

    def extract_document(self, meta, local_path):
        pdf_path = document_to_pdf(local_path)
        if pdf_path is None or not os.path.isfile(pdf_path):
            log.warning("Could not convert document: %r", meta)
            return
        try:
            self.store_pdf(meta, pdf_path, move=False)
            self.extract_pdf(meta, pdf_path)
        finally:
            if os.path.isfile(pdf_path):
                os.unlink(pdf_path)

    def ingest(self, meta, local_path):
        self.extract_document(meta, local_path)


class HtmlIngestor(DocumentIngestor):
    MIME_TYPES = ['text/html']
    EXTENSIONS = ['html', 'htm', 'asp', 'aspx', 'jsp']

    cleaner = Cleaner(scripts=True, javascript=True, style=True, links=True,
                      embedded=True, forms=True, annoying_tags=True,
                      meta=False)

    def ingest(self, meta, local_path):
        fh, out_path = mkstemp(suffix='htm')
        os.close(fh)
        with open(local_path, 'rb') as fh:
            doc = html.fromstring(fh.read())
            if not meta.has('title'):
                title = doc.findtext('.//title')
                if title is not None:
                    meta.title = title.strip()

            if not meta.has('summary'):
                summary = doc.find('.//meta[@name="description"]')
                if summary is not None and summary.get('content'):
                    meta.summary = summary.get('content')

            self.cleaner(doc)
        try:
            with open(out_path, 'w') as fh:
                fh.write(etree.tostring(doc))

            self.extract_document(meta, out_path)
        finally:
            if os.path.isfile(out_path):
                os.unlink(out_path)


class ImageIngestor(TextIngestor):
    MIME_TYPES = ['image/png', 'image/tiff', 'image/x-tiff',
                  'image/jpeg', 'image/bmp', '  image/x-windows-bmp',
                  'image/x-portable-bitmap']
    EXTENSIONS = ['gif', 'png', 'jpg', 'jpeg', 'tif', 'tiff', 'bmp',
                  'jpe', 'pbm']
    BASE_SCORE = 5

    def ingest(self, meta, local_path):
        text = extract_image(local_path)
        pdf_path = image_to_pdf(local_path)
        try:
            if pdf_path is None or not os.path.isfile(pdf_path):
                log.warning("Could not convert image: %r", meta)
                return
            self.store_pdf(meta, pdf_path)
            document = self.create_document(meta)
            self.create_page(document, text)
            self.emit(document)
        finally:
            if os.path.isfile(pdf_path):
                os.unlink(pdf_path)
