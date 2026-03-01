from app import Project, ProjectAccess, app, init_db


def main():
    if init_db is None or Project is None or ProjectAccess is None:
        raise RuntimeError("App models were not loaded correctly.")

    init_db()
    with app.app_context():
        project_count = Project.query.count()
        access_count = ProjectAccess.query.count()

        print(f"Projects: {project_count}")
        print(f"Project access rows: {access_count}")
        print("-" * 60)

        projects = Project.query.order_by(Project.id.asc()).all()
        if not projects:
            print("No projects found.")
            return

        for project in projects:
            if project.access_list:
                emails = [entry.user_email for entry in project.access_list]
            else:
                emails = [
                    email.strip()
                    for email in (project.assigned_user or "").split(",")
                    if email.strip()
                ]
            print(
                f"Project #{project.id} | name={project.name} | drive_id={project.drive_id} | users={emails}"
            )


if __name__ == "__main__":
    main()
