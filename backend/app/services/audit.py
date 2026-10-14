from sqlalchemy import event

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


# Application-level protection only; database administrators can still alter SQLite.


@event.listens_for(AuditEvent, "before_update")
@event.listens_for(AuditEvent, "before_delete")
def reject_audit_mutation(mapper, connection, target):
    raise ValueError("Audit events are append-only through the application")
