"""
Full timeline intelligence flow test.
"""

from dataclasses import dataclass
from uuid import uuid4


from app.models.timeline_event import (
    TimelineEventType,
)

from app.analysis.timeline_analyzer import (
    TimelineAnalyzer,
)

from app.analysis.temporal_pattern_detector import (
    TemporalPatternDetector,
)



@dataclass
class FakeTimelineEvent:
    """
    Lightweight event object
    for analyzer testing.
    """

    id: object

    case_id: object

    entity_id: object

    event_type: TimelineEventType

    title: str

    event_time: str



def create_event(
    time: str,
    entity_id=None,
):
    """
    Create fake timeline event.
    """

    return FakeTimelineEvent(

        id=uuid4(),

        case_id=uuid4(),

        entity_id=entity_id,

        event_type=(
            TimelineEventType.MESSAGE
        ),

        title="test",

        event_time=time,
    )



def test_full_timeline_analysis():

    entity = uuid4()


    events = [

        create_event(
            "2026-01-01T10:00:00",
            entity,
        ),

        create_event(
            "2026-01-01T10:03:00",
            entity,
        ),

        create_event(
            "2026-01-01T10:05:00",
            entity,
        ),

    ]


    analyzer = TimelineAnalyzer(
        events
    )


    assert analyzer.count_events() == 3


    activity = analyzer.get_entity_activity(
        entity
    )


    assert len(activity) == 3



    first = analyzer.get_first_event()

    last = analyzer.get_last_event()


    assert (
        first.event_time
        ==
        "2026-01-01T10:00:00"
    )


    assert (
        last.event_time
        ==
        "2026-01-01T10:05:00"
    )



    detector = TemporalPatternDetector(
        events
    )


    sequences = detector.find_rapid_sequences(
        minutes=10
    )


    assert len(sequences) == 1


    assert len(
        sequences[0]
    ) == 3