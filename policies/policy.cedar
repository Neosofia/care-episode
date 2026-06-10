permit (
    principal is care_episode::User,
    action in [Action::"care-episode:list", Action::"care-episode:create"],
    resource
);