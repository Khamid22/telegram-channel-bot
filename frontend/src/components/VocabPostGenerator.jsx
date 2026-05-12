import { BookOpen, Eye, FileText, FolderOpen, Loader2, RefreshCw, Sparkles, Upload } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client.js';

function rowLabel(row, index) {
  return row.word ? `${index + 1}. ${row.word}` : `Row ${index + 1}`;
}

export default function VocabPostGenerator({ templates, onChanged }) {
  const [catalog, setCatalog] = useState({ collections: [], sources: [] });
  const [collectionId, setCollectionId] = useState('');
  const [sourceId, setSourceId] = useState('');
  const [uploadFile, setUploadFile] = useState(null);
  const [rows, setRows] = useState([]);
  const [rowIndex, setRowIndex] = useState(0);
  const [templateId, setTemplateId] = useState('');
  const [batchName, setBatchName] = useState('');
  const [captionText, setCaptionText] = useState('');
  const [preview, setPreview] = useState(null);
  const [createdBatch, setCreatedBatch] = useState(null);
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState('');

  const currentRow = rows[rowIndex] ?? null;
  const selectedSource = catalog.sources.find((source) => String(source.id) === String(sourceId));
  const selectedTemplate = templates.find((template) => String(template.id) === String(templateId));
  const sourcesForCollection = useMemo(
    () => catalog.sources.filter((source) => !collectionId || String(source.collection_id) === String(collectionId)),
    [catalog.sources, collectionId]
  );

  useEffect(() => {
    void loadCatalog();
  }, []);

  useEffect(() => {
    if (!templateId && templates.length) {
      const active = templates.find((template) => template.is_active) || templates[0];
      setTemplateId(String(active.id));
    }
  }, [templateId, templates]);

  async function loadCatalog(refresh = false) {
    setBusy(refresh ? 'refresh' : 'catalog');
    try {
      const data = refresh ? await api.refreshDrive() : await api.driveVocabulary();
      setCatalog({ collections: data.collections ?? [], sources: data.sources ?? [] });
      if (!collectionId && data.collections?.length) {
        setCollectionId(String(data.collections[0].id));
      }
      setNotice(refresh ? 'Google Drive catalog refreshed.' : '');
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy('');
    }
  }

  async function uploadSource(event) {
    event.preventDefault();
    if (!collectionId || !uploadFile) {
      setNotice('Choose a vocabulary folder and CSV file first.');
      return;
    }
    const body = new FormData();
    body.append('collection_id', collectionId);
    body.append('file', uploadFile);
    setBusy('upload');
    try {
      const data = await api.uploadVocabularySource(body);
      setRows(data.rows ?? []);
      setRowIndex(0);
      setSourceId(String(data.source.id));
      setBatchName(data.source.name.replace(/\.csv$/i, ''));
      setCatalog((value) => ({
        ...value,
        sources: [data.source, ...value.sources.filter((source) => source.id !== data.source.id)]
      }));
      setNotice(`${data.rows?.length ?? 0} vocabulary rows loaded from Drive.`);
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy('');
    }
  }

  async function loadSource(id) {
    setSourceId(id);
    if (!id) {
      setRows([]);
      setPreview(null);
      return;
    }
    setBusy('source');
    try {
      const data = await api.vocabularySourceRows(id);
      setRows(data.rows ?? []);
      setRowIndex(0);
      setBatchName(data.source.name.replace(/\.csv$/i, ''));
      setNotice(`${data.rows?.length ?? 0} rows ready for review.`);
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy('');
    }
  }

  async function previewTemplate() {
    if (!selectedTemplate || !currentRow) {
      setNotice('Select a template and a CSV row to preview.');
      return;
    }
    setBusy('preview');
    try {
      const data = await api.previewTemplate(selectedTemplate.id, { ...currentRow, caption_text: captionText });
      setPreview(data);
      setNotice('Preview rendered from the selected template.');
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy('');
    }
  }

  async function generateBatch(event) {
    event.preventDefault();
    if (!selectedSource || !selectedTemplate || !rows.length) {
      setNotice('Load a Drive CSV source and choose a saved template first.');
      return;
    }
    setBusy('generate');
    try {
      const data = await api.generateVocabularyBatch({
        source_file_id: selectedSource.id,
        template_id: selectedTemplate.id,
        name: batchName,
        caption_text: captionText
      });
      setCreatedBatch(data.item);
      setNotice(`${data.item.generated_items} posts generated and saved to Google Drive.`);
      await onChanged();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy('');
    }
  }

  return (
    <section className="view-grid">
      <div className="toolbar">
        <div>
          <h2>Generator</h2>
          <p className="toolbar-subtitle">Prepare vocabulary batches from Google Drive CSV files before scheduling.</p>
        </div>
        <button className="primary-btn" onClick={() => loadCatalog(true)} disabled={busy === 'refresh'}>
          {busy === 'refresh' ? <Loader2 className="spin-icon" size={17} /> : <RefreshCw size={17} />}
          Refresh Drive
        </button>
      </div>

      <div className="generator-workbench">
        <form className="panel generator-source-panel" onSubmit={uploadSource}>
          <div className="panel-title"><FolderOpen size={17} /> Vocabulary source</div>
          <label>Content type
            <select value="vocabulary" disabled>
              <option value="vocabulary">Vocabulary</option>
            </select>
          </label>
          <label>Drive folder
            <select value={collectionId} onChange={(event) => setCollectionId(event.target.value)}>
              <option value="">Select folder</option>
              {catalog.collections.map((collection) => (
                <option key={collection.id} value={collection.id}>{collection.name}</option>
              ))}
            </select>
          </label>
          <label>Upload local CSV
            <input type="file" accept=".csv,text/csv" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} />
          </label>
          <button className="primary-btn" type="submit" disabled={busy === 'upload'}>
            {busy === 'upload' ? <Loader2 className="spin-icon" size={17} /> : <Upload size={17} />}
            Upload to Drive
          </button>
          <label>Or use existing Drive CSV
            <select value={sourceId} onChange={(event) => loadSource(event.target.value)}>
              <option value="">Select CSV file</option>
              {sourcesForCollection.map((source) => (
                <option key={source.id} value={source.id}>{source.name}</option>
              ))}
            </select>
          </label>
        </form>

        <form className="panel generator-setup-panel" onSubmit={generateBatch}>
          <div className="panel-title"><Sparkles size={17} /> Batch setup</div>
          <label>Saved template
            <select value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
              <option value="">Select template</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>{template.name}</option>
              ))}
            </select>
          </label>
          <label>Batch name
            <input value={batchName} onChange={(event) => setBatchName(event.target.value)} placeholder="May new words" />
          </label>
          <label>Telegram caption / hashtags
            <textarea value={captionText} onChange={(event) => setCaptionText(event.target.value)} placeholder="#vocabulary&#10;Daily vocabulary post" />
          </label>
          <div className="actions">
            <button className="ghost-btn" type="button" onClick={previewTemplate} disabled={!rows.length || busy === 'preview'}>
              {busy === 'preview' ? <Loader2 className="spin-icon" size={17} /> : <Eye size={17} />}
              Preview
            </button>
            <button className="primary-btn" type="submit" disabled={!rows.length || busy === 'generate'}>
              {busy === 'generate' ? <Loader2 className="spin-icon" size={17} /> : <Sparkles size={17} />}
              Generate all posts
            </button>
          </div>
        </form>
      </div>

      <div className="generator-review-grid">
        <div className="table-panel">
          <div className="panel-title"><FileText size={17} /> CSV review</div>
          {!rows.length ? <p className="muted">Upload or select a Drive CSV to review vocabulary rows.</p> : null}
          {rows.length ? (
            <div className="generator-word-list">
              {rows.map((row, index) => (
                <button className={index === rowIndex ? 'active' : ''} key={row.source_row_key} onClick={() => setRowIndex(index)}>
                  <span>
                    <strong>{rowLabel(row, index)}</strong>
                    <small>{row.word_type || 'word'} · {row.definition}</small>
                  </span>
                  <em>#{index + 1}</em>
                </button>
              ))}
            </div>
          ) : null}
        </div>

        <div className="preview-panel generator-preview-card">
          {preview ? <img src={preview.image_url} alt="Vocabulary template preview" /> : (
            <div className="generator-preview-empty">
              <BookOpen size={42} />
              <span>Preview the selected row before generating the full batch.</span>
            </div>
          )}
          <div className="preview-copy">
            <div className="panel-title">Preview details</div>
            {currentRow ? (
              <>
                <strong>{currentRow.word}</strong>
                <p>{currentRow.definition}</p>
                <small>{currentRow.example}</small>
              </>
            ) : <p className="muted">No row selected.</p>}
            {preview?.caption ? <pre>{preview.caption}</pre> : null}
          </div>
        </div>
      </div>

      {createdBatch ? (
        <div className="panel batch-result">
          <strong>{createdBatch.name}</strong>
          <span>{createdBatch.generated_items} Drive-backed posts are ready for the Scheduler.</span>
        </div>
      ) : null}
      {notice ? <div className="toast">{notice}</div> : null}
    </section>
  );
}
