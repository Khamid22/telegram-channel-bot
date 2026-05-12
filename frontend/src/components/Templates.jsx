import { Check, Eye, FileImage, Upload } from 'lucide-react';
import { useState } from 'react';
import { api } from '../api/client.js';

export default function Templates({ templates, onChanged }) {
  const [name, setName] = useState('');
  const [image, setImage] = useState(null);
  const [config, setConfig] = useState(null);
  const [preview, setPreview] = useState(null);

  async function upload(event) {
    event.preventDefault();
    const body = new FormData();
    body.append('name', name);
    body.append('image', image);
    if (config) body.append('config', config);
    await api.uploadTemplate(body);
    setName('');
    setImage(null);
    setConfig(null);
    event.currentTarget.reset();
    onChanged();
  }

  async function previewTemplate(id) {
    const data = await api.previewTemplate(id, {
      word: 'resilient',
      word_type: 'adjective',
      phonetic: '/rɪˈzɪl.i.ənt/',
      definition: 'Able to recover quickly after difficulty or change.',
      example: 'A resilient team keeps learning even when the plan changes.',
      level: 'B2'
    });
    setPreview(data);
  }

  return (
    <section className="view-grid">
      <div className="toolbar">
        <h2>Template Library</h2>
      </div>
      <form className="panel form-grid" onSubmit={upload}>
        <label>Name<input required value={name} onChange={(event) => setName(event.target.value)} /></label>
        <label>Image<input required type="file" accept="image/png,image/jpeg" onChange={(event) => setImage(event.target.files[0])} /></label>
        <label>JSON config<input type="file" accept="application/json" onChange={(event) => setConfig(event.target.files[0])} /></label>
        <button className="primary-btn form-submit" type="submit"><Upload size={17} /> Upload template</button>
      </form>
      {preview ? (
        <div className="preview-panel">
          <img src={preview.image_url} alt="Template preview" />
          <pre>{preview.caption}</pre>
        </div>
      ) : null}
      <div className="template-grid">
        {templates.length === 0 ? <p className="muted">No templates yet. Upload one above.</p> : null}
        {templates.map((template) => (
          <article className="template-tile" key={template.id}>
            <img src={template.image_url} alt={template.name} />
            <div>
              <h3><FileImage size={17} /> {template.name}</h3>
              <span className={`pill ${template.is_active ? 'ok' : ''}`}>{template.is_active ? 'Active' : 'Inactive'}</span>
            </div>
            <div className="actions">
              <button className="ghost-btn" onClick={() => previewTemplate(template.id)}><Eye size={17} /> Preview</button>
              <button className="primary-btn" onClick={async () => { await api.activateTemplate(template.id); onChanged(); }}><Check size={17} /> Activate</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
