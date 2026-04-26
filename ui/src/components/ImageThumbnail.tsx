import { useState, useEffect } from 'react';
import { Trash2, Star } from 'lucide-react';
import './ImageThumbnail.css';

interface ImageThumbnailProps {
  file: File;
  isHero: boolean;
  onRemove: () => void;
  onToggleHero: () => void;
}

export default function ImageThumbnail({ file, isHero, onRemove, onToggleHero }: ImageThumbnailProps) {
  const [url, setUrl] = useState<string>('');

  useEffect(() => {
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  return (
    <div className={`thumb ${isHero ? 'thumb--hero' : ''}`} id={`thumb-${file.name}`}>
      {url && <img src={url} alt={file.name} className="thumb__image" />}
      <div className="thumb__overlay">
        <button
          className={`thumb__star ${isHero ? 'thumb__star--active' : ''}`}
          onClick={(e) => {
            e.stopPropagation();
            onToggleHero();
          }}
          aria-label={isHero ? `Unmark ${file.name} as hero` : `Mark ${file.name} as hero`}
          title={isHero ? 'Remove hero' : 'Set as hero'}
        >
          <Star size={14} />
        </button>
        <button
          className="thumb__remove"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          aria-label={`Remove ${file.name}`}
          id={`remove-${file.name}`}
        >
          <Trash2 size={14} />
        </button>
      </div>
      <div className="thumb__info">
        {isHero && <Star size={10} className="thumb__hero-badge" />}
        <span className="thumb__name">{file.name}</span>
      </div>
    </div>
  );
}
