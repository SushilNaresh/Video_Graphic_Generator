import { UploadCloud } from 'lucide-react';
import { useRef, useState } from 'react';

export function UploadDropzone({
  disabled,
  progress,
  onUpload
}: {
  disabled?: boolean;
  progress: number | null;
  onUpload: (file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = useState(false);

  function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (file) onUpload(file);
  }

  return (
    <section
      className={`upload-zone ${dragging ? 'dragging' : ''} ${disabled ? 'disabled' : ''}`}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        handleFiles(event.dataTransfer.files);
      }}
      onClick={() => !disabled && inputRef.current?.click()}
    >
      <UploadCloud size={28} />
      <h3>Drop MP4 / MOV</h3>
      <p>Streams directly from disk with live progress.</p>
      {progress !== null && <progress value={progress} max={100} />}
      <input ref={inputRef} type="file" accept="video/*" onChange={(event) => handleFiles(event.target.files)} hidden />
    </section>
  );
}
