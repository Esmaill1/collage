import React, { useRef, useState, type ChangeEvent } from 'react';
import { UploadCloud } from 'lucide-react';
import ImageThumbnail from './ImageThumbnail';
import './DropZone.css';

interface DropZoneProps {
  files: File[];
  heroFiles: Set<string>;
  onFilesAdded: (newFiles: File[]) => void;
  onFileRemoved: (index: number) => void;
  onToggleHero: (filename: string) => void;
}

export default function DropZone({ files, heroFiles, onFilesAdded, onFileRemoved, onToggleHero }: DropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onFilesAdded(Array.from(e.dataTransfer.files));
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      onFilesAdded(Array.from(e.target.files));
      e.target.value = '';
    }
  };

  return (
    <div className="dropzone-wrapper">
      <div
        className={`dropzone ${isDragOver ? 'dropzone--drag-over' : ''} ${files.length > 0 ? 'dropzone--has-files' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
        id="dropzone-upload"
      >
        <div className="dropzone__icon-ring">
          <UploadCloud size={28} strokeWidth={1.5} />
        </div>
        <h3 className="dropzone__title">
          {isDragOver ? 'Drop to add images' : 'Drag & drop images'}
        </h3>
        <p className="dropzone__subtitle">
          or <span className="dropzone__link">browse files</span> · JPG, PNG, WebP
        </p>
        <input
          type="file"
          multiple
          accept="image/*"
          ref={fileInputRef}
          onChange={handleFileSelect}
          style={{ display: 'none' }}
          id="file-input"
        />
      </div>

      {files.length > 0 && (
        <div className="thumbnail-grid" id="thumbnail-grid">
          {files.map((file, idx) => (
            <ImageThumbnail
              key={`${file.name}-${file.size}-${idx}`}
              file={file}
              isHero={heroFiles.has(file.name)}
              onRemove={() => onFileRemoved(idx)}
              onToggleHero={() => onToggleHero(file.name)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
