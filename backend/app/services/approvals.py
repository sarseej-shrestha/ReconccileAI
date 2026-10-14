from app.models import Approval, Proposal
from app.services.audit import audit
from app.services.importing import DomainError
from app.services.reconciliation import verify


def review(session, proposal_id, request, reviewer, correlation_id):
    proposal = session.get(Proposal, proposal_id)
    if not proposal:
        raise DomainError("Proposal not found", 404)
    if proposal.status != "PROPOSED" or proposal.version != request.version:
        raise DomainError("Proposal state or version has changed; refresh before reviewing")
    if request.decision == "APPROVED":
        verify(session, proposal)
    session.add(
        Approval(
            proposal_id=proposal.id,
            reviewer=reviewer,
            decision=request.decision,
            reason=request.reason,
        )
    )
    previous = {"status": proposal.status, "version": proposal.version}
    proposal.status = request.decision
    proposal.version += 1
    audit(
        session,
        f"proposal_{request.decision.lower()}",
        "proposal",
        proposal.id,
        actor=reviewer,
        before=previous,
        after={"status": proposal.status, "version": proposal.version},
        reason=request.reason,
        correlation_id=correlation_id,
    )
    return {"id": proposal.id, "status": proposal.status, "version": proposal.version}
