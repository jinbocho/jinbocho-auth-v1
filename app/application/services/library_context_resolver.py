from uuid import UUID

from app.domain.entities import LibraryMembership, UserRole


def resolve_active_context(
    last_selected_library_id: UUID | None, active_memberships: list[LibraryMembership]
) -> tuple[UUID, UserRole] | None:
    """Decide which library (if any) a freshly-minted token should be scoped
    to, without requiring the user to pick one every time they log in.

    Auto-selects when there's exactly one active membership (preserves
    today's single-library UX unchanged), or when the user's last-selected
    library is still an active membership (returning multi-library user).
    Otherwise returns None — the caller must mint a context-less token and
    let the frontend show the library picker.
    """
    if len(active_memberships) == 1:
        m = active_memberships[0]
        return m.library_id, m.role
    if last_selected_library_id is not None:
        match = next((m for m in active_memberships if m.library_id == last_selected_library_id), None)
        if match is not None:
            return match.library_id, match.role
    return None
