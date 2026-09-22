import { useEffect, useMemo, useState } from 'react';
import { FileVideo, Scissors, Sparkles, Wand2 } from 'lucide-react';
import { api } from './api/client';
import { Inspector } from './components/Inspector';
import { ProjectDrawer } from './components/ProjectDrawer';
import { StatusPill } from './components/StatusPill';
import { Timeline } from './components/Timeline';
import { UploadDropzone } from './components/UploadDropzone';
import { VideoViewer } from './components/VideoViewer';
import type { MotionGraphicItem, ProjectState, ProjectSummary, RenderProgress } from './types';

export default function App() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [project, setProject] = useState<ProjectState | null>(null);
  const [selectedGraphicId, setSelectedGraphicId] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [status, setStatus] = useState('Booting studio...');
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [renderProgress, setRenderProgress] = useState<RenderProgress | null>(null);

  const selectedGraphic = useMemo(
    () => project?.graphics.find((graphic) => graphic.id === selectedGraphicId) ?? null,
    [project, selectedGraphicId]
  );

  async function refreshProjects() {
    const nextProjects = await api.listProjects();
    setProjects(nextProjects);
    return nextProjects;
  }

  async function openProject(id: string) {
    setStatus('Opening project...');
    const next = await api.getProject(id);
    setProject(next);
    setSelectedGraphicId(next.graphics[0]?.id ?? null);
    setCurrentTime(0);
    setStatus(`Opened ${next.name}`);
  }

  async function createProject() {
    setStatus('Creating project...');
    const next = await api.createProject(`Studio Project ${new Date().toLocaleTimeString()}`);
    setProject(next);
    setSelectedGraphicId(null);
    await refreshProjects();
    setStatus('New project ready');
  }

  async function deleteProject(id: string) {
    const target = projects.find((item) => item.id === id);
    if (!window.confirm(`Delete "${target?.name ?? id}" and all uploaded media, assets, renders, and state?`)) return;
    setStatus('Deleting project...');
    try {
      await api.deleteProject(id);
      const nextProjects = await refreshProjects();
      if (project?.id === id) {
        setProject(null);
        setSelectedGraphicId(null);
        setCurrentTime(0);
        setRenderProgress(null);
        if (nextProjects[0]) {
          await openProject(nextProjects[0].id);
        } else {
          await createProject();
        }
      } else {
        setStatus('Project deleted');
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Delete failed');
    }
  }

  useEffect(() => {
    (async () => {
      try {
        const summaries = await refreshProjects();
        if (summaries[0]) {
          await openProject(summaries[0].id);
        } else {
          await createProject();
        }
      } catch (error) {
        setStatus(error instanceof Error ? error.message : 'Failed to start studio');
      }
    })();
  }, []);

  async function updateProject(updater: (project: ProjectState) => ProjectState) {
    if (!project) return;
    const optimistic = updater(project);
    setProject(optimistic);
    try {
      const saved = await api.autosaveProject(optimistic);
      setProject(saved);
      setStatus('Autosaved');
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Autosave failed');
    }
  }

  async function handleUploadVideo(file: File) {
    const active = project ?? (await api.createProject());
    setProject(active);
    setUploadProgress(0);
    setStatus('Uploading video (0%)...');
    try {
      const response = await api.uploadVideo(active.id, file, (progress) => {
        setUploadProgress(progress);
        setStatus(`Uploading video (${progress}%)...`);
      });
      const fresh = response.project?.id ? response.project : await api.getProject(active.id);
      setProject({ ...fresh, id: fresh.id || active.id, captions: fresh.captions ?? [], graphics: fresh.graphics ?? [] });
      setUploadProgress(null);
      await refreshProjects();
      setStatus('Upload complete. Ready to transcribe or auto-produce.');
    } catch (error) {
      setUploadProgress(null);
      setStatus(error instanceof Error ? error.message : 'Upload failed');
    }
  }

  async function runTranscription() {
    if (!project) return;
    setStatus('Generating local transcript...');
    const next = await api.transcribe(project.id);
    setProject(next);
    setStatus('Transcript ready');
  }

  async function runAutoProduction() {
    if (!project) return;
    setStatus('Creating graphics and visual reasoning log...');
    const next = await api.autoProduce(project.id);
    setProject(next);
    setSelectedGraphicId(next.graphics[0]?.id ?? null);
    setStatus('Auto-production complete');
  }

  async function runTwelveLabsAnalysis() {
    if (!project) return;
    setStatus('Running video intelligence analysis...');
    const task = await api.analyzeTwelveLabs(project.id);
    const next = await api.getProject(project.id);
    setProject(next);
    setSelectedGraphicId(task.graphics[0]?.id ?? next.graphics[0]?.id ?? null);
    setStatus(task.message || 'Analysis ready');
  }

  async function renderBurnin() {
    if (!project) return;
    setStatus('Render queued...');
    const response = await api.renderBurnin(project.id);
    setRenderProgress({ render_id: response.render_id, status: 'queued', progress: 0, message: 'Queued' });
    const timer = window.setInterval(async () => {
      const progress = await api.getRenderProgress(project.id);
      setRenderProgress(progress);
      setStatus(`Render ${Math.round(progress.progress * 100)}% — ${progress.message}`);
      if (progress.status === 'ready' || progress.status === 'failed') {
        window.clearInterval(timer);
      }
    }, 1000);
  }

  function upsertGraphic(graphic: MotionGraphicItem) {
    updateProject((current) => ({
      ...current,
      graphics: current.graphics.map((item) => (item.id === graphic.id ? graphic : item))
    }));
  }

  const canEdit = Boolean(project);

  return (
    <main className="studio-shell">
      <aside className="left-rail">
        <div className="brand-card">
          <div className="brand-icon"><Scissors size={22} /></div>
          <div>
            <h1>AI Video Studio</h1>
            <p>WYSIWYG burn-in editor</p>
          </div>
        </div>
        <ProjectDrawer
          projects={projects}
          activeId={project?.id ?? null}
          onOpen={openProject}
          onCreate={createProject}
          onDelete={deleteProject}
        />
        <UploadDropzone disabled={!canEdit} progress={uploadProgress} onUpload={handleUploadVideo} />
      </aside>

      <section className="main-stage">
        <header className="topbar">
          <div>
            <p className="eyebrow">Project</p>
            <h2>{project?.name ?? 'Loading project...'}</h2>
          </div>
          <div className="topbar-actions">
            <StatusPill label={status} busy={status.includes('...') || status.includes('%')} />
            <button onClick={runTranscription} disabled={!canEdit} className="secondary-btn"><FileVideo size={16} /> Transcribe</button>
            <button onClick={runAutoProduction} disabled={!canEdit} className="primary-btn"><Wand2 size={16} /> Auto Produce</button>
            <button onClick={runTwelveLabsAnalysis} disabled={!canEdit} className="secondary-btn"><Sparkles size={16} /> Analyze</button>
          </div>
        </header>

        <div className="viewer-grid">
          <VideoViewer
            project={project}
            currentTime={currentTime}
            playing={playing}
            selectedGraphicId={selectedGraphicId}
            onTimeUpdate={setCurrentTime}
            onPlayingChange={setPlaying}
            onSelectGraphic={setSelectedGraphicId}
          />
          <Inspector
            project={project}
            selectedGraphic={selectedGraphic}
            onProjectChange={setProject}
            onGraphicChange={upsertGraphic}
            onStatus={setStatus}
            renderProgress={renderProgress}
            onRender={renderBurnin}
            downloadUrl={project ? api.downloadMp4Url(project.id) : null}
          />
        </div>

        <Timeline
          project={project}
          currentTime={currentTime}
          selectedGraphicId={selectedGraphicId}
          onSeek={setCurrentTime}
          onSelectGraphic={setSelectedGraphicId}
          onProjectChange={setProject}
        />
      </section>


    </main>
  );
}
