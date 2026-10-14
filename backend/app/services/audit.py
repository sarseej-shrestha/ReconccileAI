from app.models import AuditEvent


def audit(
    session,
    action,
    entity_type,
    entity_id,
    *,
    actor="system",
    before=None,
    after=None,
    reason="",
    correlation_id,
):
    session.add(
        AuditEvent(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            actor=actor,
            previous_state=before,
            new_state=after,
            reason=reason,
            correlation_id=correlation_id,
        )
    )
