"""The set_date function."""

# Standard Python Libraries
from datetime import datetime


def set_date(type_, assessment, campaign_date):
    """Set a date for a campaign."""
    if getattr(assessment, type_):
        assessment_time = datetime.strptime(
            "".join(getattr(assessment, type_).rsplit(":", 1)), "%Y-%m-%dT%H:%M:%S%z"
        )
        campaign_time = datetime.strptime(
            "".join(campaign_date.rsplit(":", 1)), "%Y-%m-%dT%H:%M:%S%z"
        )
        if (
            type_ == "start_date"
            and assessment_time > campaign_time
            or type_ == "end_date"
            and assessment_time < campaign_time
        ):
            setattr(assessment, type_, campaign_date)
    else:
        setattr(assessment, type_, campaign_date)
