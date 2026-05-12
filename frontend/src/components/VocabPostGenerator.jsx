import { useCallback, useEffect, useRef, useState } from 'react';
import Papa from 'papaparse';
import {
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  Loader2,
  Upload
} from 'lucide-react';

const SAMPLE_DATA = [
  {
    word: 'Ephemeral',
    word_type: 'adjective',
    definition: 'Lasting for a very short time; transitory and fleeting in nature.',
    example: 'The ephemeral beauty of cherry blossoms makes them all the more precious to behold.'
  },
  {
    word: 'Serendipity',
    word_type: 'noun',
    definition: 'The occurrence of finding good things by chance, without deliberately searching for them.',
    example: 'It was pure serendipity that led her to discover the hidden bookshop on that rainy afternoon.'
  },
  {
    word: 'Ameliorate',
    word_type: 'verb',
    definition: 'To make something bad or unsatisfactory better; to improve a difficult situation.',
    example: 'The new community programs were designed to ameliorate living conditions in the district.'
  },
  {
    word: 'Laconic',
    word_type: 'adjective',
    definition: 'Using very few words; brief and concise in speech or expression.',
    example: 'His laconic reply, a single nod, spoke volumes about how he truly felt.'
  }
];

const CW = 2565;
const CH = 2300;
const TEMPLATE_SRC = '/assets/templates/new-words-template.png?v=20260511';
const TEXT_COLOR = '#0d0d0d';
const SERIF = 'Georgia, "Times New Roman", serif';

const CARD_FIELDS = {
  word: { x: 385, y: 410, width: 1820, size: 160, min: 88, lineHeight: 184, weight: 'bold', maxLines: 1 },
  wordType: { x: 385, y: 610, width: 1820, size: 96, min: 62, lineHeight: 112, weight: '400', maxLines: 1 },
  definition: { x: 385, y: 900, width: 1820, size: 96, min: 62, lineHeight: 120, weight: '400', maxLines: 4 },
  example: { x: 385, y: 1450, width: 1820, size: 96, min: 60, lineHeight: 120, weight: '400', maxLines: 4 }
};

let templateImagePromise;

function loadTemplateImage() {
  if (!templateImagePromise) {
    templateImagePromise = new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error('Template image failed to load'));
      image.src = TEMPLATE_SRC;
    });
  }
  return templateImagePromise;
}

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let index = 0; index < 256; index += 1) {
    let value = index;
    for (let bit = 0; bit < 8; bit += 1) {
      value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
    }
    table[index] = value;
  }
  return table;
})();

function fontFor(field, size) {
  return `${field.weight} ${size}px ${SERIF}`;
}

function splitLongWord(ctx, word, maxWidth) {
  if (ctx.measureText(word).width <= maxWidth) {
    return [word];
  }

  const chunks = [];
  let chunk = '';
  for (const character of word) {
    if (ctx.measureText(`${chunk}${character}`).width <= maxWidth) {
      chunk += character;
    } else {
      if (chunk) chunks.push(chunk);
      chunk = character;
    }
  }
  if (chunk) chunks.push(chunk);
  return chunks;
}

function wrapLines(ctx, text, maxWidth) {
  const words = String(text || '').split(/\s+/).filter(Boolean);
  if (!words.length) return [];

  const lines = [];
  let line = words[0];
  for (const word of words.slice(1)) {
    const candidate = `${line} ${word}`;
    if (ctx.measureText(candidate).width <= maxWidth) {
      line = candidate;
    } else {
      lines.push(...splitLongWord(ctx, line, maxWidth));
      line = word;
    }
  }
  lines.push(...splitLongWord(ctx, line, maxWidth));
  return lines;
}

function drawTextBox(ctx, text, field) {
  let size = field.size;
  let lines = [];
  while (size >= field.min) {
    ctx.font = fontFor(field, size);
    lines = wrapLines(ctx, text, field.width);
    if (!field.maxLines || lines.length <= field.maxLines) {
      break;
    }
    size -= 4;
  }

  if (field.maxLines && lines.length > field.maxLines) {
    lines = lines.slice(0, field.maxLines);
    lines[lines.length - 1] = `${lines[lines.length - 1].replace(/[. ]+$/, '')}...`;
  }

  ctx.font = fontFor(field, size);
  ctx.fillStyle = TEXT_COLOR;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'top';
  lines.forEach((line, lineIndex) => {
    ctx.fillText(line, field.x, field.y + lineIndex * field.lineHeight);
  });
}

function wordTypeOf(item) {
  return item.word_type || item.type || 'noun';
}

function formatExample(example) {
  const text = String(example || '').trim();
  if (!text) return 'Example:';
  if (text.startsWith('"') || text.startsWith('“')) {
    return `Example: ${text}`;
  }
  return `Example: "${text}"`;
}

async function drawCard(canvas, item) {
  canvas.width = CW;
  canvas.height = CH;
  const ctx = canvas.getContext('2d');

  const template = await loadTemplateImage();
  ctx.drawImage(template, 0, 0, CW, CH);

  const word = String(item.word || 'Word').replace(/:$/, '').toUpperCase();
  drawTextBox(ctx, `${word}:`, CARD_FIELDS.word);
  drawTextBox(ctx, wordTypeOf(item), CARD_FIELDS.wordType);
  drawTextBox(ctx, `Definition: ${item.definition || ''}`, CARD_FIELDS.definition);
  drawTextBox(ctx, formatExample(item.example), CARD_FIELDS.example);
}

function crc32(data) {
  let crc = 0xffffffff;
  for (let index = 0; index < data.length; index += 1) {
    crc = CRC_TABLE[(crc ^ data[index]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function u16(value) {
  return [value & 0xff, (value >> 8) & 0xff];
}

function u32(value) {
  return [value & 0xff, (value >> 8) & 0xff, (value >> 16) & 0xff, (value >> 24) & 0xff];
}

function buildZip(files) {
  const encoder = new TextEncoder();
  const localParts = [];
  const centralParts = [];
  let offset = 0;

  for (const { name, data } of files) {
    const nameBytes = encoder.encode(name);
    const checksum = crc32(data);
    const size = data.length;

    const local = new Uint8Array([
      0x50, 0x4b, 0x03, 0x04,
      0x14, 0x00,
      0x00, 0x00,
      0x00, 0x00,
      0x00, 0x00, 0x00, 0x00,
      ...u32(checksum),
      ...u32(size),
      ...u32(size),
      ...u16(nameBytes.length),
      0x00, 0x00,
      ...nameBytes
    ]);

    localParts.push(local, data);
    centralParts.push(new Uint8Array([
      0x50, 0x4b, 0x01, 0x02,
      0x14, 0x00,
      0x14, 0x00,
      0x00, 0x00,
      0x00, 0x00,
      0x00, 0x00, 0x00, 0x00,
      ...u32(checksum),
      ...u32(size),
      ...u32(size),
      ...u16(nameBytes.length),
      0x00, 0x00,
      0x00, 0x00,
      0x00, 0x00,
      0x00, 0x00,
      0x00, 0x00, 0x00, 0x00,
      ...u32(offset),
      ...nameBytes
    ]));

    offset += local.length + size;
  }

  const centralStart = offset;
  const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
  const end = new Uint8Array([
    0x50, 0x4b, 0x05, 0x06,
    0x00, 0x00,
    0x00, 0x00,
    ...u16(files.length),
    ...u16(files.length),
    ...u32(centralSize),
    ...u32(centralStart),
    0x00, 0x00
  ]);

  const allParts = [...localParts, ...centralParts, end];
  const total = allParts.reduce((sum, part) => sum + part.length, 0);
  const output = new Uint8Array(total);
  let position = 0;
  for (const part of allParts) {
    output.set(part, position);
    position += part.length;
  }
  return output;
}

function dataURLtoBytes(dataURL) {
  const base64 = dataURL.split(',')[1];
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement('a'), { href: url, download: filename });
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

function normalizeRow(row) {
  const normalized = {};
  for (const key of Object.keys(row)) {
    normalized[key.trim().toLowerCase()] = String(row[key] ?? '').trim();
  }
  const wordType = normalized.word_type || normalized['word type'] || normalized.type || normalized.part_of_speech || normalized.pos || '';
  return {
    word: normalized.word || normalized.vocabulary || normalized.term || '',
    word_type: wordType,
    type: wordType,
    definition: normalized.definition || normalized.meaning || '',
    example: normalized.example || normalized['example sentence'] || ''
  };
}

function rowsFromWorksheet(worksheet) {
  const headerRow = worksheet.getRow(1);
  const headers = headerRow.values
    .slice(1)
    .map((value) => String(value ?? '').trim().toLowerCase());
  const rows = [];

  worksheet.eachRow((row, rowNumber) => {
    if (rowNumber === 1) return;
    const item = {};
    row.values.slice(1).forEach((value, valueIndex) => {
      item[headers[valueIndex] || `column_${valueIndex + 1}`] = value;
    });
    rows.push(item);
  });

  return rows;
}

export default function VocabPostGenerator() {
  const [vocab, setVocab] = useState([]);
  const [index, setIndex] = useState(0);
  const [isGenerating, setIsGenerating] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [toast, setToast] = useState(null);

  const genCanvas = useRef(null);
  const prevCanvas = useRef(null);
  const fileInput = useRef(null);

  const currentItem = vocab[index] ?? null;

  useEffect(() => {
    if (currentItem && prevCanvas.current) {
      void drawCard(prevCanvas.current, currentItem).catch((error) => {
        console.warn(error);
      });
    }
  }, [currentItem]);

  const prevRef = useCallback((node) => {
    prevCanvas.current = node;
    if (node && currentItem) {
      void drawCard(node, currentItem).catch((error) => {
        console.warn(error);
      });
    }
  }, [currentItem]);

  function notify(message, type = 'info') {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  }

  function loadRows(rows) {
    const validRows = rows.map(normalizeRow).filter((row) => row.word);
    if (!validRows.length) {
      notify('No valid rows. Check column names.', 'error');
      return;
    }
    setVocab(validRows);
    setIndex(0);
    notify(`${validRows.length} words loaded`, 'success');
  }

  function parseFile(file) {
    const extension = file.name.split('.').pop().toLowerCase();
    if (extension === 'csv') {
      Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        transformHeader: (header) => header.trim().toLowerCase(),
        complete: ({ data, errors }) => {
          if (errors.length) {
            console.warn('CSV warnings:', errors);
          }
          loadRows(data);
        },
        error: (error) => notify(`CSV error: ${error.message}`, 'error')
      });
      return;
    }

    if (['xlsx', 'xls'].includes(extension)) {
      const reader = new FileReader();
      reader.onload = async (event) => {
        try {
          const { default: ExcelJS } = await import('exceljs');
          const workbook = new ExcelJS.Workbook();
          await workbook.xlsx.load(event.target.result);
          loadRows(rowsFromWorksheet(workbook.worksheets[0]));
        } catch (error) {
          notify(`XLSX error: ${error.message}`, 'error');
        }
      };
      reader.onerror = () => notify('File read failed', 'error');
      reader.readAsArrayBuffer(file);
      return;
    }

    notify('Upload a CSV or XLSX file.', 'error');
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragOver(false);
    if (event.dataTransfer.files[0]) {
      parseFile(event.dataTransfer.files[0]);
    }
  }

  function handleInput(event) {
    if (event.target.files[0]) {
      parseFile(event.target.files[0]);
    }
    event.target.value = '';
  }

  async function downloadSingle() {
    if (!currentItem || !prevCanvas.current) return;
    try {
      await drawCard(prevCanvas.current, currentItem);
      const bytes = dataURLtoBytes(prevCanvas.current.toDataURL('image/png'));
      const safeName = (currentItem.word || 'card').replace(/[^a-zA-Z0-9]/g, '_');
      saveBlob(new Blob([bytes], { type: 'image/png' }), `${safeName}.png`);
      notify('Card saved', 'success');
    } catch (error) {
      notify(`Save failed: ${error.message}`, 'error');
    }
  }

  async function downloadAll() {
    if (!vocab.length) return;
    setIsGenerating(true);
    try {
      const canvas = genCanvas.current;
      const files = [];

      for (let itemIndex = 0; itemIndex < vocab.length; itemIndex += 1) {
        await drawCard(canvas, vocab[itemIndex]);
        const safeName = (vocab[itemIndex].word || `word_${itemIndex + 1}`).replace(/[^a-zA-Z0-9]/g, '_');
        files.push({
          name: `${String(itemIndex + 1).padStart(3, '0')}_${safeName}.png`,
          data: dataURLtoBytes(canvas.toDataURL('image/png'))
        });
      }

      saveBlob(new Blob([buildZip(files)], { type: 'application/zip' }), 'multilevel_essays_posts.zip');
      notify(`${vocab.length} cards exported`, 'success');
    } catch (error) {
      notify(`Export failed: ${error.message}`, 'error');
    } finally {
      setIsGenerating(false);
      if (currentItem && prevCanvas.current) {
        void drawCard(prevCanvas.current, currentItem).catch((error) => {
          console.warn(error);
        });
      }
    }
  }

  function downloadSampleCSV() {
    const csv = [
      'word,word_type,definition,example',
      'Ephemeral,adjective,"Lasting for a very short time; transitory.","The ephemeral beauty of cherry blossoms makes them precious."',
      'Serendipity,noun,"Finding good things by chance; a happy accident.","It was pure serendipity that led her to the hidden bookshop."',
      'Ameliorate,verb,"To make something bad or unsatisfactory better.","New programs were designed to ameliorate living conditions."',
      'Laconic,adjective,"Using very few words; brief and concise.","His laconic reply, a single nod, spoke volumes."'
    ].join('\n');
    saveBlob(new Blob([csv], { type: 'text/csv;charset=utf-8;' }), 'sample_multilevel_essays.csv');
  }

  return (
    <section className="view-grid">
      <canvas
        ref={genCanvas}
        width={CW}
        height={CH}
        className="generator-hidden-canvas"
      />

      <div className="toolbar">
        <div>
          <h2>Card Generator</h2>
          <p className="toolbar-subtitle">Create PNG Multilevel Essays cards from CSV or Excel files.</p>
        </div>
        <div className="actions">
          <button className="ghost-btn" onClick={() => { setVocab(SAMPLE_DATA); setIndex(0); notify('Sample loaded', 'success'); }}>
            <BookOpen size={17} /> Load sample
          </button>
          <button className="ghost-btn" onClick={downloadSampleCSV}>
            <Download size={17} /> Template CSV
          </button>
          <button className="primary-btn" onClick={downloadAll} disabled={!vocab.length || isGenerating}>
            {isGenerating ? <Loader2 className="spin-icon" size={17} /> : <Download size={17} />}
            {isGenerating ? 'Building ZIP' : 'Download ZIP'}
          </button>
        </div>
      </div>

      <div className="generator-layout">
        <div className="generator-column">
          <div
            className={`upload-zone ${dragOver ? 'dragging' : ''}`}
            onDrop={handleDrop}
            onDragOver={(event) => { event.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onClick={() => fileInput.current?.click()}
          >
            <Upload size={28} />
            <strong>Drop CSV or XLSX here</strong>
            <span>Columns: word, word_type, definition, example</span>
            <input ref={fileInput} type="file" accept=".csv,.xlsx,.xls" onChange={handleInput} />
          </div>

          {vocab.length ? (
            <div className="table-panel generator-list-panel">
              <div className="panel-title">{vocab.length} Words Ready</div>
              <div className="generator-word-list">
                {vocab.map((item, itemIndex) => (
                  <button
                    className={itemIndex === index ? 'active' : ''}
                    key={`${item.word}-${itemIndex}`}
                    onClick={() => setIndex(itemIndex)}
                  >
                    <span>
                      <strong>{item.word}</strong>
                      <small>{wordTypeOf(item) || 'word'}</small>
                    </span>
                    <em>#{itemIndex + 1}</em>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="empty-generator panel">
              <FileText size={44} />
              <span>No words loaded yet</span>
            </div>
          )}
        </div>

        <div className="generator-column">
          <div className="generator-preview-header">
            <span>{currentItem ? `Card ${index + 1} / ${vocab.length}` : 'Preview'}</span>
            <div className="actions">
              <button className="ghost-btn" onClick={downloadSingle} disabled={!currentItem}>
                <Download size={16} /> PNG
              </button>
              <button className="icon-btn" onClick={() => setIndex((value) => Math.max(0, value - 1))} disabled={!vocab.length || index === 0} title="Previous card">
                <ChevronLeft size={16} />
              </button>
              <button className="icon-btn" onClick={() => setIndex((value) => Math.min(vocab.length - 1, value + 1))} disabled={!vocab.length || index === vocab.length - 1} title="Next card">
                <ChevronRight size={16} />
              </button>
            </div>
          </div>

          <div className="generator-preview-shell">
            {currentItem ? (
              <canvas ref={prevRef} width={CW} height={CH} />
            ) : (
              <div className="generator-preview-empty">
                <BookOpen size={42} />
                <span>Load words to preview cards</span>
              </div>
            )}
          </div>

          {currentItem ? (
            <div className="panel generator-detail">
              <div>
                <strong>{currentItem.word}</strong>
                <span>{wordTypeOf(currentItem) || 'word'}</span>
              </div>
              <p>{currentItem.definition}</p>
              <small>"{currentItem.example}"</small>
            </div>
          ) : null}
        </div>
      </div>

      {toast ? <div className={`toast ${toast.type}`}>{toast.message}</div> : null}
    </section>
  );
}
