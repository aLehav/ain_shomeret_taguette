import bisect
import csv
import logging
from markupsafe import Markup
import os
import prometheus_client
import shutil
from sqlalchemy.orm import aliased, joinedload
import tempfile
from tornado.web import authenticated
from xml.sax.saxutils import XMLGenerator
import xlsxwriter
import zipfile

from .. import convert
from .. import database
from .. import extract
from .base import BaseHandler
from . import refi_qda


logger = logging.getLogger(__name__)


class WriteAdapter(object):
    def __init__(self, write_func):
        self.write = write_func

    def flush(self):
        pass


PROM_EXPORT = prometheus_client.Counter(
    'export_total',
    "Export",
    ['what', 'extension'],
)


def init_PROM_EXPORT(w):
    for e in convert.html_to_extensions:
        PROM_EXPORT.labels(w, e).inc(0)


def export_doc(wrapped):
    async def wrapper(self, *args):
        ext = args[-1]
        ext = ext.lower()
        name, html = wrapped(self, *args)
        mimetype, contents = convert.html_to(html, ext)
        self.set_header('Content-Type', mimetype)
        if name:
            self.set_header('Content-Disposition',
                            'attachment; filename="%s.%s"' % (name, ext))
        else:
            self.set_header('Content-Disposition', 'attachment')
        for chunk in await contents:
            self.write(chunk)
        return self.finish()
    return wrapper


class ExportHighlightsDoc(BaseHandler):
    init_PROM_EXPORT('highlights_doc')

    @authenticated
    @export_doc
    def get(self, project_id, path, ext):
        PROM_EXPORT.labels('highlights_doc', ext.lower()).inc()
        project, _ = self.get_project(project_id)

        if path:
            tag = aliased(database.Tag)
            hltag = aliased(database.HighlightTag)
            highlights = (
                self.db.query(database.Highlight)
                .options(joinedload(database.Highlight.document))
                .join(hltag, hltag.highlight_id == database.Highlight.id)
                .join(tag, hltag.tag_id == tag.id)
                .filter(tag.path.startswith(path))
                .filter(tag.project == project)
            ).all()
            name = None
        else:
            # Special case to select all highlights: we also need to select
            # highlights that have no tag at all
            document = aliased(database.Document)
            highlights = (
                self.db.query(database.Highlight)
                .join(document, document.id == database.Highlight.document_id)
                .filter(document.project == project)
            ).all()
            name = 'all_tags'

        html = self.render_string('export_highlights.html', path=path,
                                  highlights=highlights)
        return name, html


def merge_overlapping_ranges(ranges):
    """Merge overlapping ranges in a sequence.
    """
    ranges = iter(ranges)
    try:
        merged = [next(ranges)]
    except StopIteration:
        return []

    for rg in ranges:
        left = right = bisect.bisect_right(merged, rg)
        # Merge left
        while left >= 1 and rg[0] <= merged[left - 1][1]:
            rg = (min(rg[0], merged[left - 1][0]),
                  max(rg[1], merged[left - 1][1]))
            left -= 1
        # Merge right
        while (right < len(merged) and
               merged[right][0] <= rg[1]):
            rg = (min(rg[0], merged[right][0]),
                  max(rg[1], merged[right][1]))
            right += 1
        # Insert
        if left == right:
            merged.insert(left, rg)
        else:
            merged[left:right] = [rg]

    return merged


class ExportDocument(BaseHandler):
    init_PROM_EXPORT('document')

    @authenticated
    @export_doc
    def get(self, project_id, document_id, ext):
        PROM_EXPORT.labels('document', ext.lower()).inc()
        doc, _ = self.get_document(project_id, document_id, True)

        highlights = merge_overlapping_ranges((hl.start_offset, hl.end_offset)
                                              for hl in doc.highlights)

        html = self.render_string(
            'export_document.html',
            name=doc.name,
            contents=Markup(extract.highlight(doc.contents, highlights)),
        )
        # Drop non-ASCII characters from the name
        name = doc.name.encode('ascii', 'ignore').decode('ascii') or None
        return name, html


class ExportCodebookXml(BaseHandler):
    PROM_EXPORT.labels('codebook', 'qdc').inc(0)

    @authenticated
    def get(self, project_id):
        PROM_EXPORT.labels('codebook', 'qdc').inc()
        project, _ = self.get_project(project_id)
        tags = list(project.tags)
        self.set_header('Content-Type', 'text/xml; charset=utf-8')
        self.set_header('Content-Disposition',
                        'attachment; filename="codebook.qdc"')

        # http://schema.qdasoftware.org/versions/Codebook/v1.0/Codebook.xsd
        output = XMLGenerator(WriteAdapter(self.write), encoding='utf-8',
                              short_empty_elements=True)
        output.startDocument()
        output.startPrefixMapping(None, 'urn:QDA-XML:codebook:1.0')
        refi_qda.write_codebook(tags, output)
        output.endPrefixMapping(None)
        output.endDocument()
        return self.finish()


class ExportCodebookCsv(BaseHandler):
    PROM_EXPORT.labels('codebook', 'csv').inc(0)

    @authenticated
    def get(self, project_id):
        PROM_EXPORT.labels('codebook', 'csv').inc()
        project, _ = self.get_project(project_id)
        tags = list(project.tags)
        self.set_header('Content-Type', 'text/csv; charset=utf-8')
        self.set_header('Content-Disposition',
                        'attachment; filename="codebook.csv"')
        writer = csv.writer(WriteAdapter(self.write))
        writer.writerow(['tag', 'description'])
        for tag in tags:
            writer.writerow([tag.path, tag.description])
        return self.finish()


class ExportCodebookXlsx(BaseHandler):
    PROM_EXPORT.labels('codebook', 'xls').inc(0)

    @authenticated
    def get(self, project_id):
        PROM_EXPORT.labels('codebook', 'xls').inc()
        project, _ = self.get_project(project_id)
        tags = list(project.tags)
        self.set_header('Content-Type',
                        ('application/vnd.openxmlformats-officedocument.'
                         'spreadsheetml.sheet'))
        self.set_header('Content-Disposition',
                        'attachment; filename="codebook.xlsx"')
        tmp = tempfile.mkdtemp(prefix='taguette_xlsx_')
        try:
            filename = os.path.join(tmp, 'codebook.xlsx')
            workbook = xlsxwriter.Workbook(filename)
            sheet = workbook.add_worksheet('codebook')

            header = workbook.add_format({'bold': True})

            sheet.write(0, 0, 'tag', header)
            sheet.write(0, 1, 'description', header)
            sheet.set_column(0, 0, 30.0)
            sheet.set_column(1, 1, 80.0)
            for row, tag in enumerate(tags, start=1):
                sheet.write(row, 0, tag.path)
                sheet.write(row, 1, tag.description)
            workbook.close()
            with open(filename, 'rb') as fp:
                chunk = fp.read(4096)
                self.write(chunk)
                while len(chunk) == 4096:
                    chunk = fp.read(4096)
                    if chunk:
                        self.write(chunk)
            return self.finish()
        finally:
            shutil.rmtree(tmp)


class ExportCodebookDoc(BaseHandler):
    init_PROM_EXPORT('codebook')

    @authenticated
    @export_doc
    def get(self, project_id, ext):
        PROM_EXPORT.labels('codebook', ext.lower()).inc()
        project, _ = self.get_project(project_id)
        tags = list(project.tags)
        html = self.render_string('export_codebook.html', tags=tags)
        return 'codebook', html


class ZipWriter(object):
    def __init__(self, write):
        self._write = write
        self._zip = zipfile.ZipFile(self, 'w')

    def write_recursive(self, src, dst=''):
        if os.path.isdir(src):
            for name in os.listdir(src):
                self.write_recursive(os.path.join(src, name),
                                     dst + '/' + name if dst else name)
        else:
            self._zip.write(src, dst)

    def write(self, data):
        self._write(data)
        return len(data)

    def flush(self):
        return

    def close(self):
        self._zip.close()


class ExportProjectXml(BaseHandler):
    PROM_EXPORT.labels('project', 'qde').inc(0)

    @authenticated
    def get(self, project_id):
        PROM_EXPORT.labels('project', 'qde').inc()
        project, _ = self.get_project(project_id)
        tmp = tempfile.mkdtemp('taguette_qde_')
        try:
            # Write XML
            with open(os.path.join(tmp, 'Project.qde'), 'wb') as fp:
                output = XMLGenerator(fp, encoding='utf-8',
                                      short_empty_elements=True)
                output.startDocument()
                output.startPrefixMapping(None, 'urn:QDA‐XML:project:1.0')
                refi_qda.write_project(project, output)
                output.endPrefixMapping(None)
                output.endDocument()

            # Write documents

            # Send as ZIP file
            self.set_header('Content-Type', 'application/zip')
            self.set_header('Content-Disposition',
                            'attachment; filename="project.qdpx"')
            zip_writer = ZipWriter(self.write)
            zip_writer.write_recursive(tmp)
            return self.finish()
        finally:
            shutil.rmtree(tmp)
