import pytest

from app.features.communication.service import CommunicationService


class FakeCommunicationRepository:
    def list_queue(self, queue_name):
        return [{"queue": queue_name}]


def test_only_documented_support_queues_are_available():
    service = CommunicationService(FakeCommunicationRepository())
    assert service.list_queue("not_informed") == [{"queue": "not_informed"}]
    with pytest.raises(ValueError):
        service.list_queue("arbitrary")
