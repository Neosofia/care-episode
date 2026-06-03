permit (
    principal is care_episode::User,
    action,
    resource
) when {
    principal.actors.contains("operator")
};
