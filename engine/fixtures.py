from dataclasses import dataclass


REFERENCE_BYTES = bytes(range(32))
_MISMATCH = 255


@dataclass(frozen=True)
class Fixture:
    candidate: bytes
    description: str
    jitter_stddev_ns: float = 0.0
    matching_prefix_bytes: int = 0


def _candidate_with_prefix(prefix_bytes: int) -> bytes:
    if prefix_bytes == len(REFERENCE_BYTES):
        return REFERENCE_BYTES
    return REFERENCE_BYTES[:prefix_bytes] + bytes([_MISMATCH]) + bytes(
        len(REFERENCE_BYTES) - prefix_bytes - 1
    )


FIXTURES = {
    "no_match": Fixture(
        candidate=_candidate_with_prefix(0),
        description="Candidate differs at the first byte; comparison control.",
    ),
    "prefix_1": Fixture(
        candidate=_candidate_with_prefix(1),
        description="Candidate matches one leading byte before the first mismatch.",
        matching_prefix_bytes=1,
    ),
    "prefix_4": Fixture(
        candidate=_candidate_with_prefix(4),
        description="Candidate matches four leading bytes before the first mismatch.",
        matching_prefix_bytes=4,
    ),
    "full_match": Fixture(
        candidate=_candidate_with_prefix(len(REFERENCE_BYTES)),
        description="Candidate matches all 32 bytes.",
        matching_prefix_bytes=len(REFERENCE_BYTES),
    ),
    "prefix_1_jitter": Fixture(
        candidate=_candidate_with_prefix(1),
        description="One-byte prefix match with controlled measurement jitter.",
        jitter_stddev_ns=250.0,
        matching_prefix_bytes=1,
    ),
    "prefix_4_jitter": Fixture(
        candidate=_candidate_with_prefix(4),
        description="Four-byte prefix match with controlled measurement jitter.",
        jitter_stddev_ns=250.0,
        matching_prefix_bytes=4,
    ),
}


def list_fixtures() -> list[str]:
    return list(FIXTURES)
