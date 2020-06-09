"""pytest plugin configuration.

https://docs.pytest.org/en/latest/writing_plugins.html#conftest-py-plugins
"""

# Standard Python Libraries
import json

# Third-Party Libraries
import pytest

# cisagov Libraries
from models.models import (
    SMTP,
    Assessment,
    Campaign,
    Group,
    Page,
    Target,
    Template,
)

AUTO_FORWARD = """
                <html>
                    <body onload=\"document.forms[\'auto_forward\'].submit()\">
                        <form action=\"\" method=\"POST\" name=\"auto_forward\"> </form>
                </html>
               """

""" JSON Fixtures """


@pytest.fixture
def assessment_json(group_json, page_json, campaign_json):
    """Return an Assessment JSON."""
    assessment_str = json.dumps(
        {
            "id": "RVXXX1",
            "timezone": "US/Eastern",
            "domain": "bad.domain",
            "target_domains": ["target.domain"],
            "start_date": "01/01/2025 13:00",
            "end_date": "01/06/2025 19:00",
            "groups": [group_json],
            "page": page_json,
            "campaigns": [campaign_json],
        }
    )
    return json.loads(assessment_str)


@pytest.fixture
def group_json(target_json):
    """Return a Group JSON."""
    group_string = json.dumps({"name": "RVXXX1-G1", "targets": target_json})
    return json.loads(group_string)


@pytest.fixture(scope="module")
def target_json():
    """Return a Target JSON with 2 emails."""
    return json.loads(
        """[
        {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@domain.test",
            "position": "IT"
        },
        {
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jane.smith@domain.test",
            "position": "HR"
        }
    ]"""
    )


@pytest.fixture
def page_json():
    """Return a Page JSON."""
    page_str = json.dumps(
        {
            "name": "RVXXX1-AutoForward",
            "capture_credentials": True,
            "capture_passwords": False,
            "redirect_url": "redirect.domain",
            "html": AUTO_FORWARD,
        }
    )
    return json.loads(page_str)


@pytest.fixture
def campaign_json(template_json, smtp_json):
    """Return a Campaign JSON."""
    campaign_str = json.dumps(
        {
            "name": "RVXXX1-C1",
            "launch_date": "01/01/2025 13:00",
            "completed_date": "01/01/2025 14:00",
            "url": "http://bad.domain/camp1",
            "group_name": "RVXX1-G1",
            "template": template_json,
            "smtp": smtp_json,
        }
    )
    return json.loads(campaign_str)


@pytest.fixture
def template_json():
    """Return a Template JSON."""
    return json.loads(
        """{
        "name": "RVXXX1-T1-ID",
        "subject": "Campaign 1",
        "html": "<html>Body Test</html>",
        "text": "Body Test"
    }"""
    )


@pytest.fixture
def smtp_json():
    """Return an SMTP JSON."""
    return json.loads(
        """{
        "name": "RVXXX1-SP",
        "from_address": "Camp1 Phish<camp1.phish@bad.domain>",
        "host": "postfix:587",
        "interface_type": "SMTP",
        "ignore_cert": true
    }"""
    )


# Object Fixtures
@pytest.fixture
def target_object():
    """Return a single Target object."""
    return Target(
        first_name="John", last_name="Doe", email="john.doe@domain.test", position="IT"
    )


@pytest.fixture
def group_object(target_object):
    """Return a single Group object."""
    return Group(
        name="RVXXX1-G1",
        targets=[
            target_object,
            Target(
                first_name="Jane",
                last_name="Smith",
                email="jane.smith@domain.test",
                position="HR",
            ),
        ],
    )


@pytest.fixture
def smtp_object():
    """Return an SMTP object."""
    return SMTP(
        name="RVXXX1-SP",
        from_address="Camp1 Phish<camp1.phish@bad.domain>",
        host="postfix:587",
        interface_type="SMTP",
        ignore_cert=True,
    )


@pytest.fixture
def template_object():
    """Return a Template object."""
    return Template(
        name="RVXXX1-T1-ID",
        subject="Campaign 1",
        html="<html>Body Test</html>",
        text="Body Test",
    )


@pytest.fixture
def page_object():
    """Return a Page object."""
    return Page(
        name="RVXXX1-AutoForward",
        capture_credentials=True,
        capture_passwords=False,
        redirect_url="redirect.domain",
        html=AUTO_FORWARD,
    )


@pytest.fixture
def campaign_object(template_object, smtp_object):
    """Return a Campaign object."""
    return Campaign(
        name="RVXXX1-C1",
        launch_date="01/01/2025 13:00",
        completed_date="01/01/2025 14:00",
        url="http://bad.domain/camp1",
        group_name="RVXX1-G1",
        template=template_object,
        smtp=smtp_object,
    )


@pytest.fixture
def assessment_object(group_object, page_object, campaign_object):
    """Return an Assessment object."""
    return Assessment(
        id="RVXXX1",
        timezone="US/Eastern",
        domain="bad.domain",
        target_domains=["target.domain"],
        start_date="01/01/2025 13:00",
        end_date="01/06/2025 19:00",
        groups=[group_object],
        page=page_object,
        campaigns=[campaign_object],
    )


def pytest_addoption(parser):
    """Add new commandline options to pytest."""
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )


def pytest_configure(config):
    """Register new markers."""
    config.addinivalue_line("markers", "slow: mark test as slow")


def pytest_collection_modifyitems(config, items):
    """Modify collected tests based on custom marks and commandline options."""
    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
