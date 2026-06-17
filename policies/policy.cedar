// Care-episode member access (patient self, clinician roster).

// Allow patients to list and create care episodes for their own patient record.
permit (
    principal is care_episode::User,
    action in [Action::"care-episode:list", Action::"care-episode:create"],
    resource is care_episode::CareEpisode
) when {
    principal.isPatient &&
    principal.uuid == resource.patientUuid
};

// Allow clinicians to list and create care episodes for patients in their tenant.
permit (
    principal is care_episode::User,
    action in [Action::"care-episode:list", Action::"care-episode:create"],
    resource is care_episode::CareEpisode
) when {
    principal.isClinician &&
    resource has tenantId &&
    principal.tenantId == resource.tenantId
};

// Allow clinicians to list the care episode catalog for their tenant.
permit (
    principal is care_episode::User,
    action == Action::"care-episode:list",
    resource is care_episode::CareEpisodeCatalog
) when {
    principal.isClinician &&
    resource has tenantId &&
    principal.tenantId == resource.tenantId
};

// Allow demo users to list the care episode catalog.
permit (
    principal is care_episode::User,
    action == Action::"care-episode:list",
    resource is care_episode::CareEpisodeCatalog
) when {
    principal.isDemo
};

// Allow patients to create care episodes through the catalog endpoint.
permit (
    principal is care_episode::User,
    action == Action::"care-episode:create",
    resource is care_episode::CareEpisodeCatalog
) when {
    principal.isPatient
};

// Allow clinicians to create care episodes through the catalog endpoint for their tenant.
permit (
    principal is care_episode::User,
    action == Action::"care-episode:create",
    resource is care_episode::CareEpisodeCatalog
) when {
    principal.isClinician &&
    resource has tenantId &&
    principal.tenantId == resource.tenantId
};
