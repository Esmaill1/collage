import { useState, useEffect, useCallback, type ChangeEvent } from 'react';
import { Loader2, Download, ImageIcon, Sparkles } from 'lucide-react';
import SettingsPanel from './components/SettingsPanel';
import DropZone from './components/DropZone';
import './App.css';

interface Config {
  width: number;
  height: number;
  padding: number;
  bg_color: string;
  face_confidence: number;
  weight_strategy: string;
  face_padding: number;
  face_only: boolean;
  hero: boolean;
  hero_scale: number;
}

const PROGRESS_STEPS = [
  'Detecting faces…',
  'Computing layout…',
  'Cropping images…',
  'Rendering collage…',
];

function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [heroFiles, setHeroFiles] = useState<Set<string>>(new Set());
  const [config, setConfig] = useState<Config>({
    width: 2500,
    height: 3000,
    padding: 4,
    bg_color: '#1a1a1a',
    face_confidence: 0.35,
    weight_strategy: 'equal',
    face_padding: 0.35,
    face_only: false,
    hero: false,
    hero_scale: 0.45,
  });

  const [loading, setLoading] = useState(false);
  const [progressStep, setProgressStep] = useState(0);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Animated progress steps while loading
  useEffect(() => {
    if (!loading) {
      setProgressStep(0);
      return;
    }
    const interval = setInterval(() => {
      setProgressStep(prev =>
        prev < PROGRESS_STEPS.length - 1 ? prev + 1 : prev
      );
    }, 2200);
    return () => clearInterval(interval);
  }, [loading]);

  const handleConfigChange = (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    let finalValue: string | number | boolean = value;

    if (type === 'checkbox') {
      finalValue = (e.target as HTMLInputElement).checked;
    } else if (type === 'number' || type === 'range') {
      finalValue = Number(value);
    }

    setConfig(prev => ({ ...prev, [name]: finalValue }));
  };

  const toggleHeroFile = useCallback((filename: string) => {
    setHeroFiles(prev => {
      const next = new Set(prev);
      if (next.has(filename)) {
        next.delete(filename);
      } else {
        next.add(filename);
      }
      // Auto-toggle hero layout setting based on selection
      setConfig(c => ({ ...c, hero: next.size > 0 }));
      return next;
    });
  }, []);

  const handleFileRemoved = useCallback((idx: number) => {
    setFiles(prev => {
      const removed = prev[idx];
      if (removed) {
        setHeroFiles(h => {
          const next = new Set(h);
          next.delete(removed.name);
          return next;
        });
      }
      return prev.filter((_, i) => i !== idx);
    });
  }, []);

  const handleGenerate = async () => {
    if (files.length === 0) {
      setError('Please add at least one image.');
      return;
    }

    setLoading(true);
    setError(null);
    setResultUrl(null);

    const formData = new FormData();
    files.forEach(f => formData.append('files', f));

    // Append config fields
    Object.entries(config).forEach(([key, value]) => {
      formData.append(key, value.toString());
    });

    // When hero files are selected via stars, force hero mode on
    if (heroFiles.size > 0) {
      formData.set('hero', 'true');
      heroFiles.forEach(name => {
        formData.append('hero_filenames', name);
      });
    }

    try {
      const response = await fetch('http://localhost:8000/api/generate', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Failed to generate collage. Check the backend console for details.');
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      setResultUrl(url);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      {/* ---- Sidebar ---- */}
      <div className="app__sidebar">
        <SettingsPanel config={config} onChange={handleConfigChange} />
      </div>

      {/* ---- Main ---- */}
      <main className="app__main">
        {/* Header */}
        <header className="app__header" id="app-header">
          <h1 className="app__title">
            <Sparkles size={28} strokeWidth={1.5} className="app__title-icon" />
            Collage Studio
          </h1>
          <p className="app__tagline">Saliency-aware collage generator — faces always stay visible.</p>
        </header>

        {error && (
          <div className="app__error" id="error-banner" role="alert">
            {error}
          </div>
        )}

        {/* Upload */}
        <DropZone
          files={files}
          heroFiles={heroFiles}
          onFilesAdded={newFiles => setFiles(prev => [...prev, ...newFiles])}
          onFileRemoved={handleFileRemoved}
          onToggleHero={toggleHeroFile}
        />

        {/* Generate Button */}
        <button
          className="btn-generate"
          onClick={handleGenerate}
          disabled={loading || files.length === 0}
          id="btn-generate"
        >
          {loading ? (
            <>
              <Loader2 className="btn-generate__spinner" size={18} />
              <span>{PROGRESS_STEPS[progressStep]}</span>
            </>
          ) : (
            <>
              <Sparkles size={18} />
              <span>Generate Collage</span>
              {files.length > 0 && (
                <span className="btn-generate__count">{files.length} image{files.length !== 1 ? 's' : ''}</span>
              )}
            </>
          )}
        </button>

        {/* Preview */}
        <section className="preview" id="preview-section">
          {loading ? (
            <div className="preview__empty">
              <div className="preview__loader-ring"></div>
              <p className="preview__status">{PROGRESS_STEPS[progressStep]}</p>
            </div>
          ) : resultUrl ? (
            <div className="preview__result">
              <img src={resultUrl} alt="Generated Collage" className="preview__image" />
              <a
                href={resultUrl}
                download="collage.png"
                className="btn-download"
                id="btn-download"
              >
                <Download size={16} />
                Download Full Resolution
              </a>
            </div>
          ) : (
            <div className="preview__empty">
              <ImageIcon size={48} strokeWidth={1} className="preview__placeholder-icon" />
              <p>Your collage will appear here</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;