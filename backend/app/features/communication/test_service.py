import pytest

from app.core.rules import RuleViolation
from app.features.communication.repository import CommunicationRepository
from app.features.communication.service import CommunicationService


class FakeCommunicationRepository:
    def list_queue(self, queue_name):
        return [{"queue": queue_name}]


def test_only_documented_support_queues_are_available():
    service = CommunicationService(FakeCommunicationRepository())
    assert service.list_queue("not_informed") == [{"queue": "not_informed"}]
    with pytest.raises(RuleViolation):
        service.list_queue("arbitrary")


def test_communication_repository_delegates_to_support_queue_index():
    class FakeCases:
        def list_queue(self, index, partition):
            assert index == "GSI2"
            assert partition == "SUPPORT#not_informed"
            return [{"case_id": "EX-1"}]

    assert CommunicationRepository(FakeCases()).list_queue("not_informed") == [
        {"case_id": "EX-1"}
    ]
