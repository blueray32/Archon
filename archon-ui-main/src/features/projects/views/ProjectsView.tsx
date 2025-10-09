import { useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useStaggeredEntrance } from "../../../hooks/useStaggeredEntrance";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../ui/primitives";

const DeleteConfirmModal = lazy(() =>
  import("../../ui/components/DeleteConfirmModal").then((m) => ({
    default: m.DeleteConfirmModal,
  })),
);
const NewProjectModal = lazy(() =>
  import("../components/NewProjectModal").then((m) => ({
    default: m.NewProjectModal,
  })),
);
const ProjectHeader = lazy(() =>
  import("../components/ProjectHeader").then((m) => ({
    default: m.ProjectHeader,
  })),
);
const ProjectList = lazy(() =>
  import("../components/ProjectList").then((m) => ({ default: m.ProjectList })),
);
const DocsTab = lazy(() =>
  import("../documents/DocsTab").then((m) => ({ default: m.DocsTab })),
);

import {
  projectKeys,
  useDeleteProject,
  useProjects,
  useTaskCounts,
  useUpdateProject,
} from "../hooks/useProjectQueries";

const TasksTab = lazy(() =>
  import("../tasks/TasksTab").then((m) => ({ default: m.TasksTab })),
);

import type { Project } from "../types";

interface ProjectsViewProps {
  className?: string;
  "data-id"?: string;
}

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: [0.23, 1, 0.32, 1] },
  },
};

export function ProjectsView({
  className = "",
  "data-id": dataId,
}: ProjectsViewProps) {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // State management
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [activeTab, setActiveTab] = useState("tasks");
  const [isNewProjectModalOpen, setIsNewProjectModalOpen] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState<{
    id: string;
    title: string;
  } | null>(null);

  // React Query hooks
  const {
    data: projects = [],
    isLoading: isLoadingProjects,
    error: projectsError,
  } = useProjects();
  const { data: taskCounts = {}, refetch: refetchTaskCounts } = useTaskCounts();

  // Mutations
  const updateProjectMutation = useUpdateProject();
  const deleteProjectMutation = useDeleteProject();

  // Sort projects - pinned first, then alphabetically
  const sortedProjects = useMemo(() => {
    return [...(projects as Project[])].sort((a, b) => {
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      return a.title.localeCompare(b.title);
    });
  }, [projects]);

  // Handle project selection
  const handleProjectSelect = useCallback(
    (project: Project) => {
      if (selectedProject?.id === project.id) return;

      setSelectedProject(project);
      setActiveTab("tasks");
      navigate(`/projects/${project.id}`, { replace: true });
    },
    [selectedProject?.id, navigate],
  );

  // Auto-select project based on URL or default to leftmost
  useEffect(() => {
    if (!sortedProjects.length) return;

    // If there's a projectId in the URL, select that project
    if (projectId) {
      const project = sortedProjects.find((p) => p.id === projectId);
      if (project) {
        setSelectedProject(project);
        return;
      }
    }

    // Otherwise, select the first (leftmost) project
    if (
      !selectedProject ||
      !sortedProjects.find((p) => p.id === selectedProject.id)
    ) {
      const defaultProject = sortedProjects[0];
      setSelectedProject(defaultProject);
      navigate(`/projects/${defaultProject.id}`, { replace: true });
    }
  }, [sortedProjects, projectId, selectedProject, navigate]);

  // Refetch task counts when projects change
  useEffect(() => {
    if ((projects as Project[]).length > 0) {
      refetchTaskCounts();
    }
  }, [projects, refetchTaskCounts]);

  // Handle pin toggle
  const handlePinProject = async (e: React.MouseEvent, projectId: string) => {
    e.stopPropagation();
    const project = (projects as Project[]).find((p) => p.id === projectId);
    if (!project) return;

    updateProjectMutation.mutate({
      projectId,
      updates: { pinned: !project.pinned },
    });
  };

  // Handle delete project
  const handleDeleteProject = (
    e: React.MouseEvent,
    projectId: string,
    title: string,
  ) => {
    e.stopPropagation();
    setProjectToDelete({ id: projectId, title });
    setShowDeleteConfirm(true);
  };

  const confirmDeleteProject = () => {
    if (!projectToDelete) return;

    deleteProjectMutation.mutate(projectToDelete.id, {
      onSuccess: () => {
        // Success toast handled by mutation
        setShowDeleteConfirm(false);
        setProjectToDelete(null);

        // If we deleted the selected project, select another one
        if (selectedProject?.id === projectToDelete.id) {
          const remainingProjects = (projects as Project[]).filter(
            (p) => p.id !== projectToDelete.id,
          );
          if (remainingProjects.length > 0) {
            const nextProject = remainingProjects[0];
            setSelectedProject(nextProject);
            navigate(`/projects/${nextProject.id}`, { replace: true });
          } else {
            setSelectedProject(null);
            navigate("/projects", { replace: true });
          }
        }
      },
    });
  };

  const cancelDeleteProject = () => {
    setShowDeleteConfirm(false);
    setProjectToDelete(null);
  };

  // Staggered entrance animation
  const isVisible = useStaggeredEntrance([1, 2, 3], 0.15);

  return (
    <motion.div
      initial="hidden"
      animate={isVisible ? "visible" : "hidden"}
      variants={containerVariants}
      className={`max-w-full mx-auto ${className}`}
      data-id={dataId}
    >
      <Suspense
        fallback={<div className="p-2 text-sm text-zinc-500">Loading…</div>}
      >
        <ProjectHeader onNewProject={() => setIsNewProjectModalOpen(true)} />
      </Suspense>

      <Suspense
        fallback={<div className="p-2 text-sm text-zinc-500">Loading…</div>}
      >
        <ProjectList
          projects={sortedProjects}
          selectedProject={selectedProject}
          taskCounts={taskCounts}
          isLoading={isLoadingProjects}
          error={projectsError as Error | null}
          onProjectSelect={handleProjectSelect}
          onPinProject={handlePinProject}
          onDeleteProject={handleDeleteProject}
          onRetry={() =>
            queryClient.invalidateQueries({ queryKey: projectKeys.lists() })
          }
        />
      </Suspense>

      {/* Project Details Section */}
      {selectedProject && (
        <motion.div variants={itemVariants} className="relative">
          <Tabs
            defaultValue="tasks"
            value={activeTab}
            onValueChange={setActiveTab}
            className="w-full"
          >
            <TabsList>
              <TabsTrigger
                value="docs"
                className="py-3 font-mono transition-all duration-300"
                color="blue"
              >
                Docs
              </TabsTrigger>
              <TabsTrigger
                value="tasks"
                className="py-3 font-mono transition-all duration-300"
                color="orange"
              >
                Tasks
              </TabsTrigger>
            </TabsList>

            {/* Tab content */}
            <div>
              {activeTab === "docs" && (
                <TabsContent value="docs" className="mt-0">
                  <Suspense
                    fallback={
                      <div className="p-4 text-sm text-zinc-500">
                        Loading docs…
                      </div>
                    }
                  >
                    <DocsTab project={selectedProject} />
                  </Suspense>
                </TabsContent>
              )}
              {activeTab === "tasks" && (
                <TabsContent value="tasks" className="mt-0">
                  <Suspense
                    fallback={
                      <div className="p-4 text-sm text-zinc-500">
                        Loading tasks…
                      </div>
                    }
                  >
                    <TasksTab projectId={selectedProject.id} />
                  </Suspense>
                </TabsContent>
              )}
            </div>
          </Tabs>
        </motion.div>
      )}

      {/* Modals */}
      <Suspense fallback={null}>
        <NewProjectModal
          open={isNewProjectModalOpen}
          onOpenChange={setIsNewProjectModalOpen}
          onSuccess={() => refetchTaskCounts()}
        />
      </Suspense>

      {showDeleteConfirm && projectToDelete && (
        <Suspense fallback={null}>
          <DeleteConfirmModal
            itemName={projectToDelete.title}
            onConfirm={confirmDeleteProject}
            onCancel={cancelDeleteProject}
            type="project"
            open={showDeleteConfirm}
            onOpenChange={setShowDeleteConfirm}
          />
        </Suspense>
      )}
    </motion.div>
  );
}
