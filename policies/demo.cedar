// Demo bootstrap: read seeded template patient; write care data to self only.

// Allow demo users to read care episodes for the seeded template patient.
permit (
    principal is care_episode::User,
    action == Action::"care-episode:list",
    resource is care_episode::CareEpisode
) when {
    principal.isDemo &&
    resource.patientUuid == principal.demoTemplatePatientUuid
};

// Allow demo users to create care episodes only for their own patient record.
permit (
    principal is care_episode::User,
    action == Action::"care-episode:create",
    resource is care_episode::CareEpisode
) when {
    principal.isDemo &&
    principal.uuid == resource.patientUuid
};

// Allow demo users to list the care episode catalog.
permit (
    principal is care_episode::User,
    action == Action::"care-episode:list",
    resource is care_episode::CareEpisodeCatalog
) when {
    principal.isDemo
};
