permit (
    principal is care_episode::User,
    action in [Action::"care-episode:read", Action::"care-episode:create"],
    resource
);