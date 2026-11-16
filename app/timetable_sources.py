import base64
import csv
from datetime import datetime
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.request import ProxyHandler, Request, build_opener
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from .assistant import ollama_model
from config import ollama_address

FIELDS = ("day", "class", "subject", "teacher", "start", "end", "room")
MAX_ROWS = 150
MAX_TEXT = 32000
MAX_UPLOAD = 5 * 1024 * 1024
WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

WINDOWS_OCR = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1
} | Select-Object -First 1
function Receive-Ocr($operation, $type) {
  $task = $asTask.MakeGenericMethod($type).Invoke($null, @($operation))
  $task.Wait()
  $task.Result
}
$bytes = [Convert]::FromBase64String([Console]::In.ReadToEnd())
$memory = [IO.MemoryStream]::new($bytes)
$stream = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($memory)
$decoder = Receive-Ocr ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
if ($decoder.PixelWidth -gt 4096 -or $decoder.PixelHeight -gt 4096) { exit 2 }
$bitmap = Receive-Ocr ($decoder.GetSoftwareBitmapAsync([Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8,[Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied)) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
$result = Receive-Ocr ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$words = @($result.Lines | ForEach-Object { $_.Words })
$sorted = $words | Sort-Object { $_.BoundingRect.Y + $_.BoundingRect.Height / 2 }
$rows = @()
foreach ($word in $sorted) {
  $box = $word.BoundingRect
  $middle = $box.Y + $box.Height / 2
  if (!$rows.Count -or [Math]::Abs($middle - $rows[-1].Middle) -gt [Math]::Max(7, $box.Height * 0.48)) {
    $rows += @{ Middle = $middle; Words = @($word) }
  } else {
    $rows[-1].Words += $word
  }
}
foreach ($row in $rows) {
  $parts = @()
  $previous = $null
  foreach ($word in ($row.Words | Sort-Object { $_.BoundingRect.X })) {
    $box = $word.BoundingRect
    if ($previous -and ($box.X - $previous.Right) -gt [Math]::Max(12, $box.Height * 0.9)) { $parts += [char]9 }
    elseif ($previous) { $parts += " " }
    $parts += $word.Text
    $previous = $box
  }
  [Console]::WriteLine(($parts -join ""))
}
"""


def read_image(payload):
    if os.name != "nt":
        raise ValueError("Image reading requires Windows. Paste the timetable text instead.")
    exe = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    script = base64.b64encode(WINDOWS_OCR.encode("utf-16-le")).decode()
    try:
        result = subprocess.run([str(exe), "-NoProfile", "-NonInteractive", "-EncodedCommand", script],
                                input=base64.b64encode(payload), capture_output=True, timeout=18,
                                creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("Image reader unavailable. Try a clearer image or paste the timetable.") from exc
    text = result.stdout.decode("utf-8-sig", errors="replace").strip()
    if result.returncode or not text:
        raise ValueError("Could not read the image. Use a clear PNG or JPEG under 4096 pixels per side.")
    return text


def read_source(upload):
    suffix = Path(upload.filename).suffix.lower()
    content = upload.stream.read(MAX_UPLOAD + 1)
    if not content or len(content) > MAX_UPLOAD:
        raise ValueError("Upload a file between 1 byte and 5 MB.")
    if suffix in {".csv", ".txt", ".tsv"}:
        try:
            return content.decode("utf-8-sig")
        except UnicodeError as exc:
            raise ValueError("Save the text file as UTF-8.") from exc
    if suffix in {".png", ".jpg", ".jpeg"}:
        if not content.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")):
            raise ValueError("Choose a valid PNG or JPEG image.")
        return read_image(content)
    if suffix not in {".docx", ".xlsx"}:
        raise ValueError("Use Word .docx, Excel .xlsx, CSV, text, PNG or JPEG.")
    try:
        with ZipFile(BytesIO(content)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 20 * 1024 * 1024:
                raise ValueError("The document expands beyond the import size limit.")
            if suffix == ".docx":
                root = ElementTree.fromstring(archive.read("word/document.xml"))
                def words(element):
                    return " ".join(node.text or "" for node in element.iter(WORD + "t"))
                body = root.find(WORD + "body")
                if body is None:
                    raise ValueError("The document has no timetable content.")
                lines = []
                for element in body:
                    if element.tag == WORD + "tbl":
                        for row in element.findall(WORD + "tr"):
                            lines.append("\t".join(words(cell) for cell in row.findall(WORD + "tc")))
                    elif element.tag == WORD + "p":
                        lines.append(words(element))
                return "\n".join(lines)
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True, keep_links=False)
        try:
            output = StringIO()
            writer = csv.writer(output)
            for row in workbook.active.iter_rows(max_row=MAX_ROWS + 2, max_col=8, values_only=True):
                values = list(row)
                while values and values[-1] is None:
                    values.pop()
                if values:
                    writer.writerow(values)
            return output.getvalue()
        finally:
            workbook.close()
    except (BadZipFile, InvalidFileException, KeyError, ElementTree.ParseError, OSError) as exc:
        raise ValueError("The Word or Excel file could not be read.") from exc


def table_rows(text):
    if len(text) > MAX_TEXT:
        raise ValueError("Split this timetable into smaller imports.")
    rows = []
    for index, line in enumerate((x.strip() for x in text.splitlines() if x.strip()), 1):
        delimiter = next((x for x in ("\t", "|", ",") if x in line), None)
        if delimiter is None:
            raise ValueError(f"Line {index}: separate timetable columns with commas, tabs or pipes.")
        values = [value.strip() for value in next(csv.reader([line], delimiter=delimiter))]
        if index == 1 and values[0].casefold() in {"day", "weekday"}:
            continue
        if len(values) not in (6, 7):
            raise ValueError(f"Line {index}: expected Day, Class, Subject, Teacher, Start, End and optional Room.")
        rows.append(dict(zip(FIELDS, (values + [""])[:7])))
    if not rows or len(rows) > MAX_ROWS:
        raise ValueError(f"Enter between 1 and {MAX_ROWS} timetable entries.")
    return rows


def draft_with_ai(text):
    return extract_rows(text, FIELDS, "Extract timetable rows only. Copy names and rooms exactly. "
                        "Use HH:MM when stated. Leave unknown fields blank. Do not invent rows or times.")


def extract_rows(text, fields, instructions):
    model = ollama_model()
    if not model or len(text) > 8000:
        return None
    schema = {"type": "object", "properties": {"rows": {"type": "array", "maxItems": MAX_ROWS,
              "items": {"type": "object", "properties": {key: {"type": "string"} for key in fields},
                        "required": list(fields), "additionalProperties": False}}}, "required": ["rows"]}
    payload = {
        "model": model, "stream": False, "format": schema,
        "options": {"temperature": 0, "num_predict": 1800},
        "messages": [
            {"role": "system", "content": instructions + " Fields: " + ", ".join(fields)},
            {"role": "user", "content": text},
        ],
    }
    call = Request(f"http://{ollama_address()}/api/chat", headers={"Content-Type": "application/json"},
                   data=json.dumps(payload).encode())
    try:
        with build_opener(ProxyHandler({})).open(call, timeout=45) as response:
            data = json.loads(response.read(65536))
        rows = json.loads(data["message"]["content"])["rows"]
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def parse_time(value):
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(value.strip(), fmt).strftime("%H:%M")
        except ValueError:
            continue
    raise ValueError("Enter times such as 08:30 or 8:30 AM.")


def normalized(value):
    return re.sub(r"[\W_]+", " ", str(value).casefold()).strip()
