// Allow platform operators full access to all care-episode actions and resources.
permit (
    principal is care_episode::User,
    action,
    resource
) when {
    principal.isOperator
};

// Allow platform operators to list the care episode catalog.
permit (
    principal is care_episode::User,
    action == Action::"care-episode:list",
    resource is care_episode::CareEpisodeCatalog
) when {
    principal.isOperator
};

// Allow platform operators to create care episodes through the catalog endpoint.
permit (
    principal is care_episode::User,
    action == Action::"care-episode:create",
    resource is care_episode::CareEpisodeCatalog
) when {
    principal.isOperator
};
