import { Plus, Trash2 } from 'lucide-react';
import type { ProjectSummary } from '../types';

export function ProjectDrawer({
  projects,
  activeId,
  onOpen,
  onCreate,
  onDelete
}: {
  projects: ProjectSummary[];
  activeId: string | null;
  onOpen: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
}) {
  return (
    <section className="panel project-drawer">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Workspace</p>
          <h3>Projects</h3>
        </div>
        <button className="icon-btn" onClick={onCreate} title="Create project"><Plus size={16} /></button>
      </div>
      <div className="project-list">
        {projects.map((project) => (
          <div
            key={project.id}
            className={`project-row ${project.id === activeId ? 'active' : ''}`}
          >
            <button className="project-open" onClick={() => onOpen(project.id)}>
              <strong>{project.name}</strong>
              <span>{project.has_source_video ? `${project.duration_seconds.toFixed(1)}s` : 'No video yet'}</span>
            </button>
            <button className="project-delete" onClick={() => onDelete(project.id)} title={`Delete ${project.name}`}>
              <Trash2 size={15} />
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
