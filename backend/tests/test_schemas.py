import pytest
from pydantic import ValidationError

from backend.app.schemas.auth import UserCreate
from backend.app.schemas.submission import SubmissionCreate

VALID = dict(label="Run 1", implementation="vulnerable", fixture_id="no_match", sample_size=100)


def test_valid_submission():
    assert SubmissionCreate(**VALID).warmup_runs == 50


def test_sample_size_out_of_range_rejected():
    with pytest.raises(ValidationError):
        SubmissionCreate(**{**VALID, "sample_size": 10})


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        SubmissionCreate(**VALID, is_admin=True)


def test_bad_label_rejected():
    with pytest.raises(ValidationError):
        SubmissionCreate(**{**VALID, "label": "<script>alert(1)</script>"})


def test_weak_password_rejected():
    with pytest.raises(ValidationError):
        UserCreate(username="bob_1", password="alllettersnodigits", role="operator")