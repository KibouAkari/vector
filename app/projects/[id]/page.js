import {
  notFound
} from "next/navigation";

import {
  requireSession
} from "../../../lib/auth";

import {
  db
} from "../../../lib/db";

import { canAccessProject, canEditProject } from "../../../lib/identity";

import {
  humanBytes,
  initializeFileDatabase
} from "../../../lib/project-files";

import {
  projectIndexStats
} from "../../../lib/project-index";

import Sidebar
  from "../../../components/sidebar";

import ProjectWorkbench
  from "./project-workspace";

export const dynamic = "force-dynamic";

export default async function ProjectPage({
  params
}) {
  const session =
    await requireSession();

  const {
    id
  } =
    await params;

  if (!await canAccessProject(session, id)) {
    notFound();
  }

  const canEdit = await canEditProject(session, id);

  await initializeFileDatabase();

  const projectResult =
    await db.query(
      `
        SELECT *
        FROM projects
        WHERE id = $1
      `,
      [
        id
      ]
    );

  if (
    projectResult.rowCount ===
    0
  ) {
    notFound();
  }

  const filesResult =
    await db.query(
      `
        SELECT
          id,
          original_name,
          mime_type,
          extension,
          size_bytes,
          sha256,
          previewable,
          created_at

        FROM project_files

        WHERE
          project_id = $1

        ORDER BY
          created_at DESC
      `,
      [
        id
      ]
    );

  const taskResult =
    await db.query(
      `
        SELECT
          id,
          title,
          description,
          status,
          created_at,
          updated_at

        FROM tasks

        WHERE
          project_id = $1

        ORDER BY
          created_at DESC

        LIMIT 100
      `,
      [
        id
      ]
    );

  const conversationsResult =
    await db.query(
      `
        SELECT
          id,
          title,
          created_at,
          updated_at

        FROM conversations

        WHERE
          project_id = $1

        ORDER BY
          updated_at DESC

        LIMIT 50
      `,
      [
        id
      ]
    );

  const activityResult =
    await db.query(
      `
        SELECT
          id,
          actor,
          action,
          resource,
          details,
          source,
          created_at

        FROM audit_log

        WHERE
          resource = $1

          OR
          details->>'projectId' =
          $1

        ORDER BY
          created_at DESC

        LIMIT 60
      `,
      [
        id
      ]
    );

  const indexStats =
    await projectIndexStats(
      id
    );

  const files =
    filesResult.rows.map(
      (
        file
      ) => ({
        ...file,

        size_bytes:
          Number(
            file.size_bytes
          ),

        created_at:
          file.created_at
            ?.toISOString?.() ||
          file.created_at
      })
    );

  const totalBytes =
    files.reduce(
      (
        total,
        file
      ) =>
        total +
        Number(
          file.size_bytes
        ),
      0
    );

  const project = {
    ...projectResult.rows[0],

    created_at:
      projectResult.rows[0]
        .created_at
        ?.toISOString?.() ||
      projectResult.rows[0]
        .created_at,

    updated_at:
      projectResult.rows[0]
        .updated_at
        ?.toISOString?.() ||
      projectResult.rows[0]
        .updated_at
  };

  const tasks =
    taskResult.rows.map(
      (
        task
      ) => ({
        ...task,

        created_at:
          task.created_at
            ?.toISOString?.() ||
          task.created_at,

        updated_at:
          task.updated_at
            ?.toISOString?.() ||
          task.updated_at
      })
    );

  const conversations =
    conversationsResult.rows.map(
      (
        conversation
      ) => ({
        ...conversation,

        created_at:
          conversation.created_at
            ?.toISOString?.() ||
          conversation.created_at,

        updated_at:
          conversation.updated_at
            ?.toISOString?.() ||
          conversation.updated_at
      })
    );

  const activity =
    activityResult.rows.map(
      (
        item
      ) => ({
        ...item,

        created_at:
          item.created_at
            ?.toISOString?.() ||
          item.created_at
      })
    );

  return (
    <div className="vector-shell vector-projects-page">

      <Sidebar
        session={
          session
        }
      />

      <main className="main workbench-main">

        <ProjectWorkbench
          canEdit={canEdit}
          project={
            project
          }

          files={
            files
          }

          tasks={
            tasks
          }

          conversations={[]}

          activity={
            activity
          }

          stats={{
            totalBytes,
            totalFiles:
              files.length,

            indexedFiles:
              Number(
                indexStats.indexed_files ||
                0
              ),

            chunks:
              Number(
                indexStats.chunks ||
                0
              ),

            storage:
              humanBytes(
                totalBytes
              )
          }}
        />

      </main>

    </div>
  );
}

