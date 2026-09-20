from datetime import UTC, datetime

import pytest

from coldchain.domain import IncidentState, InvalidStateTransition, transition
from coldchain.domain.incidents import require_utc


def test_valid_incident_state_machine_path() -> None:
    state = IncidentState.OPEN
    for target in (
        IncidentState.EVIDENCE_COLLECTED,
        IncidentState.AWAITING_APPROVAL,
        IncidentState.APPROVED,
        IncidentState.EXECUTING,
        IncidentState.RESOLVED,
    ):
        state = transition(state, target)
    assert state is IncidentState.RESOLVED


@pytest.mark.parametrize("terminal", [IncidentState.REJECTED, IncidentState.RESOLVED])
def test_terminal_incident_states_reject_transitions(terminal: IncidentState) -> None:
    with pytest.raises(InvalidStateTransition):
        transition(terminal, IncidentState.OPEN)


def test_utc_timestamp_boundary() -> None:
    aware = datetime(2026, 9, 19, tzinfo=UTC)
    assert require_utc(aware) == aware
    with pytest.raises(ValueError, match="timezone"):
        require_utc(datetime(2026, 9, 19))
