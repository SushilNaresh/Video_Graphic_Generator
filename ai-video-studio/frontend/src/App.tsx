import { useCallback, useEffect, useMemo, useState } from 'react';
import { FileVideo, Scissors, Sparkles, Wand2 } from 'lucide-react';
import { api } from './api/client';
import { ActivityLog } from './components/ActivityLog';
import { Inspector } from './components/Inspector';
import { ProjectDrawer } from './components/ProjectDrawer';
import { StatusPill } from './components/StatusPill';
import { Timeline } from './components/Timeline';
import { UploadDropzone } from './components/UploadDropzone';
import { VideoViewer } from './components/VideoViewer';
import type { ActivityEntry, MotionGraphicItem, ProjectState, ProjectSummary, RenderProgress, SkillNote } from './types';

export default function App() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [project, setProject] = useState<ProjectState | null>(null);
  const [selectedGraphicId, setSelectedGraphicId] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [status, setStatus] = useState('Booting studio...');
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [renderProgress, setRenderProgress] = useState<RenderProgress | null>(null);
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);
  const [skillNotes, setSkillNotes] = useState<SkillNote[]>([]);

  const selectedGraphic = useMemo(
    () => project?.graphics.find((g) => g.id === selectedGraphicId) ?? null,
    [project, selectedGraphicId]
  );

  const refreshActivity = useCallback(async (id: string) => {
    try {
      const [log, notes] = await Promise.all([api.getActivityLog(id), api.getSkillNotes(id)]);
      setActivityLog(log);
      setSkillNotes(notes);
    } catch { /* silent */ }
  }, []);

  async function refreshProjects() {
    const next = await api.listProjects();
    setProjects(next);
    return next;
  }

  async function openProject(id: string) {
    setStatus('Opening project...');
    const next = await api.getProject(id);
    setProject(next);
    setSelectedGraphicId(next.graphics[0]?.id ?? null);
    setCurrentTime(0);
    setStatus(`Opened ${next.name}`);
    await refreshActivity(id);
  }

  async function createProject() {
    setStatus('Creating project...');
    const next = await api.createProject(`Studio Project ${new Date().toLocaleTimeString()}`);
    setProject(next);
    setSelectedGraphicId(null);
    setActivityLog([]);
    await refreshProjects();
    setStatus('New project ready');
  }

  async function deleteProject(id: string) {
    const target = projects.find((p) => p.id === id);
    if (!window.confirm(`Delete "${target?.name ?? id}" and all uploaded media, assets, renders, and state?`)) return;
    setStatus('Deleting project...');
    try {
      await api.deleteProject(id);
      const next = await refreshProjects();
      if (project?.id === id) {
        setProject(null); setSelectedGraphicId(null); setCurrentTime(0); setRenderProgress(null); setActivityLog([]);
        if (next[0]) await openProject(next[0].id); else await createProject();
      } else { setStatus('Project deleted'); }
    } catch (err) { setStatus(err instanceof Error ? err.message : 'Delete failed'); }
  }

  useEffect(() => {
    (async () => {
      try {
        const summaries = await refreshProjects();
        if (summaries[0]) await openProject(summaries[0].id); else await createProject();
      } catch (err) { setStatus(err instanceof Error ? err.message : 'Failed to start studio'); }
    })();
  }, []);

  async function updateProject(updater: (p: ProjectState) => ProjectState) {
    if (!project) return;
    const optimistic = updater(project);
    setProject(optimistic);
    try {
      const saved = await api.autosaveProject(optimistic);
      setProject(saved);
      setStatus('Autosaved');
    } catch (err) { setStatus(err instanceof Error ? err.message : 'Autosave failed'); }
  }

  async function handleUploadVideo(file: File) {
    const active = project ?? (await api.createProject());
    setProject(active);
    setUploadProgress(0);
    setStatus('Uploading video (0%)...');
    try {
      const res = await api.uploadVideo(active.id, file, (pct) => {
        setUploadProgress(pct);
        setStatus(`Uploading video (${pct}%)...`);
      });
      const fresh = res.project?.id ? res.project : await api.getProject(active.id);
      setProject({ ...fresh, id: fresh.id || active.id, captions: fresh.captions ?? [], graphics: fresh.graphics ?? [] });
      setUploadProgress(null);
      await refreshProjects();
      setStatus('Upload complete. Ready to transcribe or auto-produce.');
    } catch (err) { setUploadProgress(null); setStatus(err instanceof Error ? err.message : 'Upload failed'); }
  }

  async function runTranscription() {
    if (!project) return;
    setStatus('Transcribing audio with Whisper...');
    const next = await api.transcribe(project.id);
    setProject(next);
    setStatus(`Transcript ready — ${next.captions.length} segments`);
    await refreshActivity(project.id);
  }

  async function runAutoProduction() {
    if (!project) return;
    setStatus('Creating graphics and visual reasoning log...');
    const next = await api.autoProduce(project.id);
    setProject(next);
    setSelectedGraphicId(next.graphics[0]?.id ?? null);
    setStatus(`Auto-production complete — ${next.graphics.length} graphics placed`);
    await refreshActivity(project.id);
  }

  async function runTwelveLabsAnalysis() {
    if (!project) return;
    setStatus('Running video intelligence analysis...');
    const task = await api.analyzeTwelveLabs(project.id);
    const next = await api.getProject(project.id);
    setProject(next);
    setSelectedGraphicId(task.graphics[0]?.id ?? next.graphics[0]?.id ?? null);
    setStatus(task.message || 'Analysis ready');
    await refreshActivity(project.id);
  }

  async function renderBurnin() {
    if (!project) return;
    setStatus('Render queued...');
    const res = await api.renderBurnin(project.id);
    setRenderProgress({ render_id: res.render_id, status: 'queued', progress: 0, message: 'Queued' });
    const timer = window.setInterval(async () => {
      const prog = await api.getRenderProgress(project.id);
      setRenderProgress(prog);
      setStatus(`Render ${Math.round(prog.progress * 100)}% — ${prog.message}`);
      if (prog.status === 'ready' || prog.status === 'failed') {
        window.clearInterval(timer);
        await refreshActivity(project.id);
      }
    }, 1000);
  }

  async function handleAddSkillNote(graphicId: string, templateId: string, trigger: string, note: string) {
    if (!project) return;
    await api.addSkillNote(project.id, { graphic_id: graphicId, template_id: templateId, trigger, note });
    await refreshActivity(project.id);
  }

  async function handleClearLog() {
    if (!project) return;
    await api.clearActivityLog(project.id);
    setActivityLog([]);
  }

  function upsertGraphic(graphic: MotionGraphicItem) {
    updateProject((p) => ({ ...p, graphics: p.graphics.map((g) => (g.id === graphic.id ? graphic : g)) }));
  }

  async function handleAddGraphic(payload: object) {
    if (!project) return;
    setStatus('Adding graphic...');
    const next = await api.addGraphic(project.id, payload);
    setProject(next);
    setSelectedGraphicId(next.graphics[next.graphics.length - 1]?.id ?? null);
    setStatus('Graphic added');
    await refreshActivity(project.id);
  }

  async function handleDeleteGraphic(graphicId: string) {
    if (!project) return;
    setStatus('Removing graphic...');
    const next = await api.deleteGraphic(project.id, graphicId);
    setProject(next);
    setSelectedGraphicId(null);
    setStatus('Graphic removed');
    await refreshActivity(project.id);
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
        <ProjectDrawer projects={projects} activeId={project?.id ?? null} onOpen={openProject} onCreate={createProject} onDelete={deleteProject} />
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
            project={project} currentTime={currentTime} playing={playing}
            selectedGraphicId={selectedGraphicId}
            onTimeUpdate={setCurrentTime} onPlayingChange={setPlaying} onSelectGraphic={setSelectedGraphicId}
          />
          <Inspector
            project={project} selectedGraphic={selectedGraphic} currentTime={currentTime}
            onProjectChange={setProject} onGraphicChange={upsertGraphic}
            onGraphicDelete={handleDeleteGraphic} onGraphicAdd={handleAddGraphic}
            onStatus={setStatus} renderProgress={renderProgress}
            onRender={renderBurnin} downloadUrl={project ? api.downloadMp4Url(project.id) : null}
          />
        </div>

        <Timeline
          project={project} currentTime={currentTime} selectedGraphicId={selectedGraphicId}
          onSeek={setCurrentTime} onSelectGraphic={setSelectedGraphicId} onProjectChange={setProject}
        />

        <ActivityLog entries={activityLog} skillNotes={skillNotes} onJumpTo={setCurrentTime} onAddNote={handleAddSkillNote} onClearLog={handleClearLog} />
      </section>
    </main>
  );
}
