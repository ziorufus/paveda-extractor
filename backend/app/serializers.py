from .schemas import ProjectOut, SetOut, UserOut, VersionOut


def user_out(user):
    data = UserOut.model_validate(user)
    data.project_ids = sorted(project.id for project in user.projects)
    return data


def project_out(project, include_users=True):
    data = ProjectOut.model_validate(project)
    data.version_count = len(project.versions)
    data.latest_version = VersionOut.model_validate(project.versions[0]) if project.versions else None
    data.user_ids = sorted(user.id for user in project.users) if include_users else []
    return data


def set_out(project_set):
    return SetOut(
        id=project_set.id,
        name=project_set.name,
        description=project_set.description,
        project_ids=[project.id for project in project_set.projects],
    )
